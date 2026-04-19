import json
import os
import urllib.request
import urllib.parse
import psycopg2

def get_db():
    return psycopg2.connect(os.environ['DATABASE_URL'])

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
    target_url = body.get('target_url', '').strip()
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

    # Добавляем CDN cookies к заголовкам основного запроса
    if cdn_cookies:
        request_headers['Cookie'] = cdn_cookies

    # Делаем GET к target_url
    status_code = 0
    response_text = ''
    try:
        req = urllib.request.Request(target_url, headers=request_headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            status_code = r.status
            response_text = r.read().decode('utf-8', errors='replace')[:4000]
    except urllib.error.HTTPError as e:
        status_code = e.code
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