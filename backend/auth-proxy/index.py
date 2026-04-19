import json
import os
import ssl
import urllib.request
import urllib.parse
import pg8000.native

CA_CERT = '/usr/local/share/ca-certificates/yandex-internal-ca.crt'

def get_db():
    dsn = os.environ['DATABASE_URL']
    parsed = urllib.parse.urlparse(dsn)

    ssl_context = None
    if os.path.exists(CA_CERT):
        ssl_context = ssl.create_default_context(cafile=CA_CERT)
        ssl_context.check_hostname = False

    return pg8000.native.Connection(
        user=parsed.username,
        password=parsed.password,
        host=parsed.hostname,
        port=5432,
        database=parsed.path.lstrip('/'),
        ssl_context=ssl_context,
    )

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

    # Делаем GET к target_url с заголовком Authorization
    status_code = 0
    response_text = ''
    try:
        req = urllib.request.Request(target_url, headers={'Authorization': runtime_token or 'Bearer none'})
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
        conn.run(
            "INSERT INTO proxy_log (target, status, response) VALUES (:target, :status, :response)",
            target=target_url, status=status_code, response=response_text
        )
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
            'db_debug': db_debug,
            'db_error': db_error,
            'incoming_headers': event.get('headers', {}),
        })
    }