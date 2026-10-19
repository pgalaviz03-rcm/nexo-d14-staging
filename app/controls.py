import os, time, json, logging, threading, asyncio
from collections import OrderedDict
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select, text
from .models import UsageCounter
from .config import cloud


def take_quota(session, pid, action, limit, period='day'):
    """Atomic PostgreSQL admission; attempts persist even when the operation fails."""
    now = datetime.now(timezone.utc)
    bucket = now.strftime('%Y-%m-%d' if period == 'day' else '%Y-%m-%dT%H:%M')
    if session.bind.dialect.name == 'postgresql':
        admitted = session.execute(text('''INSERT INTO usage_counters(project_id,action,bucket,used)
            VALUES (:pid,:action,:bucket,1)
            ON CONFLICT (project_id,action,bucket) DO UPDATE SET used=usage_counters.used+1
            WHERE usage_counters.used < :lim RETURNING used'''),
            {'pid': pid, 'action': action, 'bucket': bucket, 'lim': limit}).scalar()
    else:
        row = session.scalar(select(UsageCounter).where(UsageCounter.project_id==pid,
            UsageCounter.action==action, UsageCounter.bucket==bucket))
        admitted = not row or row.used < limit
        if admitted:
            if row: row.used += 1
            else: session.add(UsageCounter(project_id=pid,action=action,bucket=bucket,used=1))
    session.commit()
    if not admitted:
        raise HTTPException(429, 'Límite del proyecto alcanzado', headers={'Retry-After': '60'})


class WindowLimiter:
    """Single-instance global and login buckets. Never keys on spoofable forwarding headers."""
    def __init__(self):
        self.buckets = OrderedDict()
        self.lock = threading.Lock()

    def accept(self, key, cap):
        window = int(time.monotonic() // 60)
        with self.lock:
            old_window, used = self.buckets.get(key, (window, 0))
            used = used if old_window == window else 0
            self.buckets[key] = (window, used+1)
            self.buckets.move_to_end(key)
            while len(self.buckets) > 4096:
                self.buckets.popitem(last=False)
            return used < cap


class Guard:
    """ASGI body bounds apply before multipart parsing; secure headers include errors."""
    def __init__(self, app, script_hash):
        self.app = app
        self.script_hash = script_hash
        self.limiter = WindowLimiter()
        logger=logging.getLogger('nexo')
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            logger.addHandler(logging.StreamHandler())
        logger.propagate=False

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        from starlette.responses import JSONResponse
        headers = dict(scope['headers'])
        path = scope['path']
        method = scope['method']
        async def reply(status, detail):
            return await JSONResponse({'detail': detail}, status_code=status)(scope, receive, secure_send)
        async def secure_send(message):
            if message['type'] == 'http.response.start':
                hs = list(message.get('headers', []))
                csp = ("default-src 'self'; script-src 'self' '"+self.script_hash+"'; "
                    "style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; "
                    "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
                hs += [(b'content-security-policy', csp.encode()), (b'x-content-type-options', b'nosniff'),
                    (b'referrer-policy', b'no-referrer'), (b'x-frame-options', b'DENY'),
                    (b'cache-control', b'no-store'), (b'permissions-policy', b'camera=(), microphone=(), geolocation=()')]
                if cloud(): hs.append((b'strict-transport-security', b'max-age=31536000'))
                message['headers'] = hs
                logging.getLogger('nexo').info(json.dumps({'event':'http', 'method':method,
                    'route': 'auth' if '/auth/' in path else 'api' if path.startswith('/api') else 'static',
                    'status':message['status'], 'ms':round((time.monotonic()-started)*1000)}))
            await send(message)
        started = time.monotonic()
        if cloud():
            origin = os.environ['NEXO_PUBLIC_ORIGIN'].rstrip('/')
            from urllib.parse import urlsplit
            if headers.get(b'host', b'').decode() != urlsplit(origin).netloc:
                return await reply(400, 'Host no permitido')
            if method not in ('GET','HEAD','OPTIONS') and headers.get(b'origin', b'').decode() != origin:
                return await reply(403, 'Origen no permitido')
        if not self.limiter.accept('global', 300):
            return await reply(429, 'Límite temporal de solicitudes')
        if '/api/auth/' in path and method == 'POST':
            # Platform rate-limits supplement this global ceiling; no password/email in logs.
            if not self.limiter.accept('auth', 20):
                return await reply(429, 'Espera antes de volver a intentar')
        max_bytes = 13*1024*1024 if '/datasets' in path else 600_000 if path.endswith('/articles/import') else 32_000
        try:
            if int(headers.get(b'content-length', b'0')) > max_bytes:
                return await reply(413, 'Solicitud demasiado grande')
        except ValueError:
            return await reply(400, 'Longitud inválida')
        # Bound streaming bodies before the framework parses files or JSON.
        messages=[]; total=0
        if method not in ('GET','HEAD','OPTIONS'):
            deadline=time.monotonic()+20
            while True:
                try:
                    remaining=deadline-time.monotonic()
                    if remaining<=0:raise asyncio.TimeoutError()
                    message = await asyncio.wait_for(receive(),timeout=remaining)
                except asyncio.TimeoutError:
                    return await reply(408, 'Tiempo de carga agotado')
                if message['type'] == 'http.disconnect': return
                total += len(message.get('body', b''))
                if total > max_bytes or len(messages)>=1024:return await reply(413, 'Solicitud demasiado grande o fragmentada')
                messages.append(message)
                if not message.get('more_body', False): break
        async def replay():
            return messages.pop(0) if messages else await receive()
        await self.app(scope, replay, secure_send)
