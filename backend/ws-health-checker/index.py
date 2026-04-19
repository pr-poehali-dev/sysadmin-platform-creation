# 2026-04-19
import asyncio
import json
import os
import time
import urllib.request
import urllib.error

try:
    import websockets
    WS_AVAILABLE = True
except ImportError:
    WS_AVAILABLE = False

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False


async def check_websocket(name: str, url: str, headers: dict, send: str | None, timeout: int) -> dict:
    """Проверяет WebSocket-сервис: подключение, отправка сообщения, ожидание ответа."""
    start = time.monotonic()
    try:
        extra_headers = list(headers.items()) if headers else []
        async with asyncio.timeout(timeout):
            async with websockets.connect(url, additional_headers=extra_headers) as ws:
                if send:
                    await ws.send(send)
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=timeout)
                except asyncio.TimeoutError:
                    response = ''
        latency_ms = int((time.monotonic() - start) * 1000)
        return {
            'name': name,
            'status': 'ok',
            'response': str(response)[:2000],
            'latency_ms': latency_ms,
        }
    except Exception as e:
        latency_ms = int((time.monotonic() - start) * 1000)
        return {
            'name': name,
            'status': 'error',
            'response': str(e)[:2000],
            'latency_ms': latency_ms,
        }


async def check_http(name: str, url: str, headers: dict, timeout: int) -> dict:
    """Проверяет HTTP-сервис: GET-запрос с заголовками."""
    start = time.monotonic()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout), ssl=False) as resp:
                body = await resp.text()
                latency_ms = int((time.monotonic() - start) * 1000)
                return {
                    'name': name,
                    'status': 'ok',
                    'response': body[:2000],
                    'latency_ms': latency_ms,
                }
    except Exception as e:
        latency_ms = int((time.monotonic() - start) * 1000)
        return {
            'name': name,
            'status': 'error',
            'response': str(e)[:2000],
            'latency_ms': latency_ms,
        }


async def run_checks(checks: list) -> list:
    tasks = []
    for check in checks:
        name = check.get('name', '')
        url = check.get('url', '')
        headers = check.get('headers') or {}
        send = check.get('send')
        timeout = int(check.get('timeout') or 5)

        if url.startswith('ws://') or url.startswith('wss://'):
            tasks.append(check_websocket(name, url, headers, send, timeout))
        else:
            tasks.append(check_http(name, url, headers, timeout))

    return await asyncio.gather(*tasks)


def handler(event: dict, context) -> dict:
    """
    Опрашивает список сервисов (WebSocket и HTTP) и возвращает их статус.
    Авторизация через заголовок Authorization: Bearer {HEALTH_CHECK_TOKEN}.
    """
    cors_headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    }

    if event.get('httpMethod') == 'OPTIONS':
        return {'statusCode': 200, 'headers': cors_headers, 'body': ''}

    # Авторизация
    expected_token = os.environ.get('HEALTH_CHECK_TOKEN', '')
    auth_header = event.get('headers', {}).get('Authorization') or event.get('headers', {}).get('authorization', '')
    bearer = auth_header.removeprefix('Bearer ').strip()
    if expected_token and bearer != expected_token:
        return {
            'statusCode': 401,
            'headers': {**cors_headers, 'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Unauthorized'}),
        }

    body = json.loads(event.get('body') or '{}')
    checks = body.get('checks', [])

    if not checks:
        return {
            'statusCode': 400,
            'headers': {**cors_headers, 'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'checks array is required'}),
        }

    results = asyncio.run(run_checks(checks))

    return {
        'statusCode': 200,
        'headers': {**cors_headers, 'Content-Type': 'application/json'},
        'body': json.dumps(results),
    }