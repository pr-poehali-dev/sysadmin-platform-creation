import json
import os
import urllib.parse
import pg8000.native

def get_db():
    dsn = os.environ['DATABASE_URL']
    parsed = urllib.parse.urlparse(dsn)
    return pg8000.native.Connection(
        user=parsed.username,
        password=parsed.password,
        host=parsed.hostname,
        port=parsed.port or 5432,
        database=parsed.path.lstrip('/')
    )

def handler(event: dict, context) -> dict:
    """
    Возвращает последние 50 записей из таблицы proxy_log.
    Защищён ADMIN_TOKEN.
    """
    cors_headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Authorization',
    }

    if event.get('httpMethod') == 'OPTIONS':
        return {'statusCode': 200, 'headers': cors_headers, 'body': ''}

    admin_token = os.environ.get('ADMIN_TOKEN', '')
    auth_header = event.get('headers', {}).get('X-Authorization', '') or event.get('headers', {}).get('Authorization', '')
    token = auth_header.replace('Bearer ', '').strip()
    if not admin_token or token != admin_token:
        return {'statusCode': 401, 'headers': cors_headers, 'body': json.dumps({'error': 'Unauthorized'})}

    conn = get_db()
    rows = conn.run("SELECT id, target, status, response, ts FROM proxy_log ORDER BY ts DESC LIMIT 50")
    conn.close()

    logs = [
        {'id': r[0], 'target': r[1], 'status': r[2], 'response': r[3], 'ts': r[4].isoformat() if r[4] else None}
        for r in rows
    ]

    return {
        'statusCode': 200,
        'headers': {**cors_headers, 'Content-Type': 'application/json'},
        'body': json.dumps({'logs': logs})
    }
