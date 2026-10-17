"""Compress bounded, read-only cloud representations inside the auth boundary."""
import re

from starlette.middleware.gzip import GZipMiddleware

_SNAPSHOT = re.compile(r'^/api/accounts/[^/]+/roles/[^/]+/snapshot/[^/]+$')
_PUBLIC = re.compile(r'^/api/public/games/[^/]+/(events|news)$')
_TEXT = {'application/json', 'application/javascript', 'text/javascript', 'text/css', 'image/svg+xml'}


class CloudReadCompression:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '')
        if (scope['type'] != 'http' or scope.get('method') != 'GET'
                or any(k.lower() == b'range' for k, _ in scope.get('headers', []))
                or not (path.startswith('/assets/') or _SNAPSHOT.fullmatch(path) or _PUBLIC.fullmatch(path))):
            return await self.app(scope, receive, send)

        bypass = False

        async def guarded_app(scope, receive, gzip_send):
            async def choose(message):
                nonlocal bypass
                if message['type'] == 'http.response.start':
                    headers = dict(message.get('headers', []))
                    length = headers.get(b'content-length', b'')
                    media = headers.get(b'content-type', b'').decode('latin1').split(';')[0]
                    eligible = (message['status'] == 200 and media in _TEXT
                                and length.isdigit() and 1024 <= int(length) <= 8 * 1024 * 1024)
                    if not eligible and b'content-encoding' not in headers:
                        # Starlette bypasses existing encodings. Strip this internal
                        # sentinel before sending, preserving true streaming responses.
                        bypass = True
                        message = {**message, 'headers': [*message.get('headers', []), (b'content-encoding', b'identity')]}
                await gzip_send(message)
            await self.app(scope, receive, choose)

        async def representation_send(message):
            if message['type'] == 'http.response.start':
                headers = list(message.get('headers', []))
                if bypass:
                    headers = [(k,v) for k,v in headers if k.lower() != b'content-encoding']
                elif dict(headers).get(b'content-encoding') == b'gzip':
                    headers = [(k, b'W/' + v if k.lower() == b'etag' and not v.startswith(b'W/') else v) for k,v in headers]
                message = {**message, 'headers': headers}
            await send(message)

        await GZipMiddleware(guarded_app, minimum_size=1024, compresslevel=5)(scope, receive, representation_send)
