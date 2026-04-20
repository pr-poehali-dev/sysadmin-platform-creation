import base64
import json
import os
import shutil
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path
import psycopg2

def get_db():
    return psycopg2.connect(os.environ['DATABASE_URL'])


def _git_sync(body: dict, cors_headers: dict) -> dict:  # v2
    repo_url = body.get('repo_url', '').strip()
    auth_mode = body.get('auth_mode', 'token').strip()
    auth_value = body.get('auth_value', '').strip()
    branch = body.get('branch', 'main').strip()

    if not repo_url:
        return {'statusCode': 400, 'headers': {**cors_headers, 'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'repo_url is required'})}

    if auth_mode not in ('token', 'ssh_key', 'askpass'):
        return {'statusCode': 400, 'headers': {**cors_headers, 'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'auth_mode must be token, ssh_key or askpass'})}

    clone_dir = '/tmp/config-repo'
    if os.path.exists(clone_dir):
        shutil.rmtree(clone_dir)

    clone_url = repo_url
    env = os.environ.copy()

    if auth_mode == 'token':
        parsed = urllib.parse.urlparse(repo_url)
        netloc = f"{auth_value}@{parsed.hostname}"
        if parsed.port:
            netloc += f":{parsed.port}"
        clone_url = urllib.parse.urlunparse(parsed._replace(netloc=netloc))

    elif auth_mode == 'ssh_key':
        key_path = '/tmp/git-key'
        with open(key_path, 'wb') as f:
            f.write(base64.b64decode(auth_value))
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
        capture_output=True, text=True, env=env, timeout=30,
    )

    if result.returncode != 0:
        stderr = result.stderr.replace(auth_value, '***') if auth_value else result.stderr
        return {'statusCode': 200, 'headers': {**cors_headers, 'Content-Type': 'application/json'},
                'body': json.dumps({'status': 'error', 'error': stderr.strip(), 'files': [], 'config_contents': {}})}

    all_files = []
    config_contents = {}
    config_exts = {'.json', '.yaml', '.yml'}

    for p in sorted(Path(clone_dir).rglob('*')):
        if p.is_file() and '.git' not in p.parts:
            rel = str(p.relative_to(clone_dir))
            all_files.append(rel)
            if p.suffix in config_exts:
                try:
                    config_contents[rel] = p.read_text(encoding='utf-8', errors='replace')
                except Exception:
                    config_contents[rel] = None

    return {'statusCode': 200, 'headers': {**cors_headers, 'Content-Type': 'application/json'},
            'body': json.dumps({'status': 'ok', 'files': all_files, 'config_contents': config_contents})}

def handler(event: dict, context) -> dict:
    """
    Прокси с авторизацией: принимает target_url, делает GET-запрос с токеном Lambda Runtime,
    логирует результат в proxy_log, возвращает HTTP статус ответа.
    Защищён ADMIN_TOKEN.
    """
    cors_headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Authorization',
    }

    if event.get('httpMethod') == 'OPTIONS':
        return {'statusCode': 200, 'headers': cors_headers, 'body': ''}

    # Проверка ADMIN_TOKEN
    admin_token = os.environ.get('ADMIN_TOKEN', '')
    auth_header = event.get('headers', {}).get('X-Authorization', '') or event.get('headers', {}).get('Authorization', '')
    token = auth_header.replace('Bearer ', '').strip()
    if not admin_token or token != admin_token:
        return {'statusCode': 401, 'headers': cors_headers, 'body': json.dumps({'error': 'Unauthorized'})}

    body = json.loads(event.get('body') or '{}')
    action = body.get('action', '').strip()

    if action == 'git_sync':
        return _git_sync(body, cors_headers)

    target_url = body.get('target_url', '').strip()
    method = body.get('method', 'GET').upper()
    if method not in ('GET', 'POST', 'PUT', 'PATCH', 'DELETE'):
        method = 'GET'
    request_body_data = body.get('request_body')
    custom_headers = body.get('headers') if isinstance(body.get('headers'), dict) else None
    if not target_url:
        return {'statusCode': 400, 'headers': cors_headers, 'body': json.dumps({'error': 'target_url required'})}

    # Получаем токен из Lambda Runtime API
    runtime_token = ''
    auth_method = 'none'
    runtime_api = os.environ.get('AWS_LAMBDA_RUNTIME_API', '')
    if runtime_api:
        try:
            creds_url = f'http://{runtime_api}/2018-06-01/runtime/credentials'
            with urllib.request.urlopen(creds_url, timeout=3) as r:
                runtime_token = r.read().decode('utf-8')
            if runtime_token:
                auth_method = 'lambda_runtime'
        except Exception:
            runtime_token = ''

    # Формируем заголовки для запроса
    if custom_headers:
        request_headers = {str(k): str(v) for k, v in custom_headers.items()}
        auth_method = 'custom_headers'
    else:
        request_headers = {'Authorization': runtime_token or 'Bearer none'}

    # Preflight: GET на корень хоста чтобы получить CDN cookies
    cdn_cookies = ''
    try:
        parsed = urllib.parse.urlparse(target_url)
        host_root = f'{parsed.scheme}://{parsed.netloc}/'
        preflight_req = urllib.request.Request(host_root, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(preflight_req, timeout=5) as r:
            set_cookie = r.headers.get('Set-Cookie', '')
            if set_cookie:
                cdn_cookies = set_cookie
    except Exception:
        pass

    # Мержим CDN cookies с HEALTH_CHECK_COOKIE из env
    env_cookie = os.environ.get('HEALTH_CHECK_COOKIE', '').strip()
    all_cookies = '; '.join(filter(None, [cdn_cookies, env_cookie]))
    if all_cookies:
        request_headers['Cookie'] = all_cookies

    # Делаем запрос к target_url
    status_code = 0
    response_text = ''
    try:
        encoded_body = None
        if method in ('POST', 'PUT', 'PATCH') and request_body_data is not None:
            if isinstance(request_body_data, (dict, list)):
                encoded_body = json.dumps(request_body_data).encode('utf-8')
                request_headers.setdefault('Content-Type', 'application/json')
            else:
                encoded_body = str(request_body_data).encode('utf-8')
        req = urllib.request.Request(target_url, data=encoded_body, headers=request_headers, method=method)
        with urllib.request.urlopen(req, timeout=10) as r:
            status_code = r.status
            response_text = r.read().decode('utf-8', errors='replace')[:4000]
    except urllib.error.HTTPError as e:
        status_code = e.code
        try:
            response_text = e.read().decode('utf-8', errors='replace')[:4000]
        except Exception:
            response_text = str(e.reason)
    except Exception as e:
        status_code = 0
        response_text = str(e)

    # Парсим DSN для отладки (без пароля)
    _dsn = os.environ.get('DATABASE_URL', '')
    _p = urllib.parse.urlparse(_dsn)
    db_debug = {
        'host': _p.hostname,
        'port': _p.port,
        'database': _p.path.lstrip('/'),
        'user': _p.username,
    }

    # Сохраняем в БД (опционально — не блокирует ответ при ошибке)
    db_logged = False
    db_error = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO proxy_log (target, status, response) VALUES (%s, %s, %s)",
            (target_url, status_code, response_text)
        )
        conn.commit()
        cur.close()
        conn.close()
        db_logged = True
    except Exception as e:
        db_error = str(e)

    return {
        'statusCode': 200,
        'headers': {**cors_headers, 'Content-Type': 'application/json'},
        'body': json.dumps({
            'status': status_code,
            'response_body': response_text,
            'response_length': len(response_text),
            'db_logged': db_logged,
            'auth_method': auth_method,
            'auth_token_length': len(runtime_token),
            'cdn_cookies_received': bool(cdn_cookies),
            'db_debug': db_debug,
            'db_error': db_error,
            'incoming_headers': event.get('headers', {}),
        })
    }