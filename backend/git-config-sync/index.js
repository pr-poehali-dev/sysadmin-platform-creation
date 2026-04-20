'use strict';

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const { URL } = require('url');

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, X-Admin-Token',
};

function json(statusCode, body) {
  return {
    statusCode,
    headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  };
}

function walkDir(dir) {
  const results = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === '.git') continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...walkDir(full));
    } else {
      results.push(full);
    }
  }
  return results;
}

module.exports.handler = async function (event, context) {
  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 200, headers: CORS_HEADERS, body: '' };
  }

  const adminToken = process.env.ADMIN_TOKEN || '';
  const incomingToken = (event.headers || {})['X-Admin-Token'] || '';
  if (adminToken && incomingToken !== adminToken) {
    return json(401, { error: 'Unauthorized' });
  }

  const body = JSON.parse(event.body || '{}');
  const { repo_url, auth_mode = 'token', auth_value = '', branch = 'main' } = body;

  if (!repo_url) return json(400, { error: 'repo_url is required' });
  if (!['token', 'ssh_key', 'askpass'].includes(auth_mode)) {
    return json(400, { error: 'auth_mode must be token, ssh_key or askpass' });
  }

  const cloneDir = '/tmp/config-repo';
  if (fs.existsSync(cloneDir)) fs.rmSync(cloneDir, { recursive: true, force: true });

  let cloneUrl = repo_url;

  if (auth_mode === 'token') {
    const u = new URL(repo_url);
    u.username = auth_value;
    cloneUrl = u.toString();
  } else if (auth_mode === 'ssh_key') {
    const keyPath = '/tmp/git-key';
    fs.writeFileSync(keyPath, Buffer.from(auth_value, 'base64'));
    fs.chmodSync(keyPath, 0o600);
    process.env.GIT_SSH_COMMAND = `ssh -i ${keyPath} -o StrictHostKeyChecking=no`;
  } else if (auth_mode === 'askpass') {
    const askpassPath = '/tmp/git-askpass.sh';
    fs.writeFileSync(askpassPath, auth_value, { encoding: 'utf8' });
    fs.chmodSync(askpassPath, 0o755);
    process.env.GIT_ASKPASS = askpassPath;
  }

  try {
    execSync(
      `git clone --depth 1 --branch ${branch} ${cloneUrl} ${cloneDir}`,
      { stdio: 'pipe', timeout: 30000 }
    );
  } catch (err) {
    const stderr = (err.stderr ? err.stderr.toString() : err.message).replace(auth_value || '\x00', '***');
    return json(200, { status: 'error', error: stderr.trim(), files: [], config_contents: {} });
  }

  const CONFIG_EXTS = new Set(['.json', '.yaml', '.yml']);
  const allFiles = [];
  const configContents = {};

  for (const fullPath of walkDir(cloneDir).sort()) {
    const rel = path.relative(cloneDir, fullPath);
    allFiles.push(rel);
    if (CONFIG_EXTS.has(path.extname(fullPath))) {
      try {
        configContents[rel] = fs.readFileSync(fullPath, 'utf8');
      } catch {
        configContents[rel] = null;
      }
    }
  }

  return json(200, { status: 'ok', files: allFiles, config_contents: configContents });
};
