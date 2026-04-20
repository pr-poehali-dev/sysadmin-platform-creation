import asyncio
import json
import os
import re
import ssl
import time

import websockets


def parse_target(target: str) -> tuple[str, int, str]:
    """Разбирает target вида IP:port или host:port, возвращает (host, port, path)."""
    # Убираем схему если есть
    raw = re.sub(r'^wss?://', '', target)
    path = '/'
    if '/' in raw:
        idx = raw.index('/')
        path = raw[idx:]
        raw = raw[:idx]
    if raw.startswith('['):
        # IPv6
        m = re.match(r'^\[(.+)\]:(\d+)$', raw)
        if m:
            return m.group(1), int(m.group(2)), path
    if ':' in raw:
        parts = raw.rsplit(':', 1)
        return parts[0], int(parts[1]), path
    return raw, 443, path


async def do_ws_check(target: str, sni: str, message: str | None, headers: dict, timeout: int, scheme: str, use_ssl: bool) -> dict:
    """Подключается по WS/WSS к target, использует sni как server_hostname в TLS (только для wss)."""
    host, port, path = parse_target(target)

    use_tls = use_ssl and scheme != 'ws'
    ssl_ctx = None
    if use_tls:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

    url = f"{'wss' if use_tls else 'ws'}://{host}:{port}{path}"
    extra_headers = list(headers.items()) if headers else []

    connect_kwargs = {
        'ssl': ssl_ctx,
        'additional_headers': extra_headers,
    }
    if use_tls:
        connect_kwargs['server_hostname'] = sni or host

    start = time.monotonic()
    tls_version = None
    tls_cipher = None
    cert_subject = None
    response = None

    async with asyncio.timeout(timeout):
        async with websockets.connect(url, **connect_kwargs) as ws:
            # Извлекаем TLS-данные через transport (websockets 14+ API)
            try:
                ssl_obj = ws.transport.get_extra_info('ssl_object')
                if ssl_obj:
                    tls_version = ssl_obj.version()
                    cipher_info = ssl_obj.cipher()
                    tls_cipher = cipher_info[0] if cipher_info else None
                    cert = ssl_obj.getpeercert()
                    if cert:
                        subject = dict(x[0] for x in cert.get('subject', []))
                        cert_subject = subject.get('commonName') or str(subject)
            except Exception:
                pass

            if message:
                await ws.send(message)

            try:
                response = await asyncio.wait_for(ws.recv(), timeout=timeout)
            except asyncio.TimeoutError:
                response = ''

    latency_ms = int((time.monotonic() - start) * 1000)
    return {
        'status': 'ok',
        'response': str(response) if response is not None else '',
        'latency_ms': latency_ms,
        'tls_version': tls_version,
        'tls_cipher': tls_cipher,
        'cert_subject': cert_subject,
    }


def handler(event: dict, context) -> dict:
    """
    TLS/WebSocket монитор для внутренних сервисов за CDN.
    Подключается к target (IP:port) с отдельным SNI hostname для корректного TLS handshake.
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
    target = body.get('target', '').strip()
    sni = body.get('sni', '').strip()
    message = body.get('message')
    headers = dict(body.get('headers')) if isinstance(body.get('headers'), dict) else {}
    cookies = body.get('cookies', '').strip()
    if cookies:
        headers['Cookie'] = cookies
    timeout = int(body.get('timeout') or 10)
    scheme = body.get('scheme', 'wss').lower()
    if scheme not in ('ws', 'wss'):
        scheme = 'wss'
    use_ssl = body.get('use_ssl', True)
    if not isinstance(use_ssl, bool):
        use_ssl = str(use_ssl).lower() not in ('false', '0', 'no')

    if not target:
        return {
            'statusCode': 400,
            'headers': {**cors_headers, 'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'target is required (IP:port or host:port)'}),
        }

    try:
        result = asyncio.run(do_ws_check(target, sni, message, headers, timeout, scheme, use_ssl))
    except Exception as e:
        result = {
            'status': 'error',
            'response': str(e)[:2000],
            'latency_ms': 0,
            'tls_version': None,
            'tls_cipher': None,
            'cert_subject': None,
        }

    return {
        'statusCode': 200,
        'headers': {**cors_headers, 'Content-Type': 'application/json'},
        'body': json.dumps(result),
    }