import base64
import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse, urlunparse


def handler(event: dict, context) -> dict:
    """
    Клонирует приватный git-репозиторий и возвращает список файлов и содержимое конфигов.
    Поддерживает аутентификацию через token, ssh_key (base64) или askpass-скрипт.
    Авторизация через заголовок X-Admin-Token.
    """
    cors_headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, X-Admin-Token',
    }

    if event.get('httpMethod') == 'OPTIONS':
        return {'statusCode': 200, 'headers': cors_headers, 'body': ''}

    admin_token = os.environ.get('ADMIN_TOKEN', '')
    incoming_token = (event.get('headers') or {}).get('X-Admin-Token', '')
    if admin_token and incoming_token != admin_token:
        return {
            'statusCode': 401,
            'headers': {**cors_headers, 'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Unauthorized'}),
        }

    body = json.loads(event.get('body') or '{}')
    repo_url = body.get('repo_url', '').strip()
    auth_mode = body.get('auth_mode', 'token').strip()
    auth_value = body.get('auth_value', '').strip()
    branch = body.get('branch', 'main').strip()

    if not repo_url:
        return {
            'statusCode': 400,
            'headers': {**cors_headers, 'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'repo_url is required'}),
        }

    if auth_mode not in ('token', 'ssh_key', 'askpass'):
        return {
            'statusCode': 400,
            'headers': {**cors_headers, 'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'auth_mode must be token, ssh_key or askpass'}),
        }

    clone_dir = '/tmp/config-repo'
    if os.path.exists(clone_dir):
        shutil.rmtree(clone_dir)

    env = os.environ.copy()
    clone_url = repo_url

    if auth_mode == 'token':
        parsed = urlparse(repo_url)
        netloc_with_token = f"{auth_value}@{parsed.hostname}"
        if parsed.port:
            netloc_with_token += f":{parsed.port}"
        clone_url = urlunparse(parsed._replace(netloc=netloc_with_token))

    elif auth_mode == 'ssh_key':
        key_path = '/tmp/git-ssh-key'
        key_bytes = base64.b64decode(auth_value)
        with open(key_path, 'wb') as f:
            f.write(key_bytes)
        os.chmod(key_path, 0o600)
        env['GIT_SSH_COMMAND'] = f'ssh -i {key_path} -o StrictHostKeyChecking=no'

    elif auth_mode == 'askpass':
        askpass_path = '/tmp/git-askpass.sh'
        with open(askpass_path, 'w') as f:
            f.write(auth_value)
        os.chmod(askpass_path, 0o755)
        env['GIT_ASKPASS'] = askpass_path

    result = subprocess.run(
        ['git', 'clone', '--depth', '1', '--branch', branch, clone_url, clone_dir],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )

    if result.returncode != 0:
        stderr = result.stderr.replace(auth_value, '***') if auth_value else result.stderr
        return {
            'statusCode': 200,
            'headers': {**cors_headers, 'Content-Type': 'application/json'},
            'body': json.dumps({
                'status': 'error',
                'error': stderr.strip(),
                'files': [],
                'config_contents': {},
            }),
        }

    all_files = []
    config_contents = {}
    config_exts = {'.json', '.yaml', '.yml'}

    repo_path = Path(clone_dir)
    for p in sorted(repo_path.rglob('*')):
        if p.is_file() and '.git' not in p.parts:
            rel = str(p.relative_to(repo_path))
            all_files.append(rel)
            if p.suffix in config_exts:
                try:
                    config_contents[rel] = p.read_text(encoding='utf-8', errors='replace')
                except Exception:
                    config_contents[rel] = None

    return {
        'statusCode': 200,
        'headers': {**cors_headers, 'Content-Type': 'application/json'},
        'body': json.dumps({
            'status': 'ok',
            'files': all_files,
            'config_contents': config_contents,
        }),
    }