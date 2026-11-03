"""Anonymous synthetic workspaces with a shared D1 inference allowance."""

import base64
from http.cookies import CookieError, SimpleCookie
import os
from pathlib import Path
import re
import secrets
import tempfile
import threading
import time
import shutil
from urllib.parse import urlsplit

from hosted import HostedDemo
from public_ai_budget import PublicAIBudget
from public_ai_completion import guarded_completion


class LiveWorkspace(HostedDemo):
    fixture_page = False


class PublicDemo:
    idle_seconds = 1800

    def __init__(self, origin, budget, model, key):
        self.origin = origin
        self.budget = budget
        self.model = model
        self.key = key
        self.storage = tempfile.TemporaryDirectory(prefix='orderthread-public-')
        self.password = secrets.token_urlsafe(32)
        self.authorization = 'Basic ' + base64.b64encode(
            ('judge:' + self.password).encode()).decode()
        self.sessions = {}
        self.lock = threading.Lock()

    def __call__(self, env, start_response):
        def reply(status, body):
            start_response(status, HostedDemo.security_headers() + [
                ('Content-Type', 'text/plain'), ('Content-Length', str(len(body)))])
            return [body]

        path = env.get('PATH_INFO')
        method = env.get('REQUEST_METHOD')
        if path == '/healthz' and method == 'GET':
            return reply('200 OK', b'OK')
        if env.get('HTTP_HOST') != urlsplit(self.origin).netloc:
            return reply('400 Bad Request', b'Unexpected host.')
        if path in ('/api/video-preview', '/api/video-frame', '/api/catalogue/preview'):
            return reply('403 Forbidden', b'Unavailable in the public demo.')
        try:
            cookie = SimpleCookie(env.get('HTTP_COOKIE', '')).get('__Host-orderthread')
        except CookieError:
            cookie = None
        session_id = cookie.value if cookie else ''
        with self.lock:
            now = time.monotonic()
            for token, (workspace, last_seen) in list(self.sessions.items()):
                if now - last_seen >= self.idle_seconds and workspace.lock.acquire(blocking=False):
                    try:
                        shutil.rmtree(workspace.directory)
                        del self.sessions[token]
                    finally:
                        workspace.lock.release()
            entry = self.sessions.get(session_id)
            demo = entry[0] if entry else None
            new_session = demo is None
            if new_session:
                if path != '/' or method != 'GET':
                    return reply('403 Forbidden', b'Open the demo page first.')
                if len(self.sessions) >= 16:
                    return reply('503 Service Unavailable', b'Demo capacity reached.')
                session_id = secrets.token_urlsafe(32)
                demo = LiveWorkspace(Path(self.storage.name) / session_id, self.origin, self.password)
                demo.app.ai_completion = guarded_completion(demo.app, self.budget, self.model, self.key)
                demo.app.provider_status = lambda: {
                    'configured': True, 'default_provider': 'baseten', 'error': None,
                    'providers': [{'id': 'baseten', 'name': 'Baseten', 'configured': True,
                                   'model': self.model, 'input_modalities': ['text', 'image', 'audio'],
                                   'output_modalities': ['text']}],
                }
            self.sessions[session_id] = (demo, now)
        private = dict(env, HTTP_AUTHORIZATION=self.authorization)
        if path != '/' or method != 'GET':
            return demo(private, start_response)
        response = []
        body = b''.join(demo(private, lambda status, headers: response.append((status, headers))))
        status, headers = response[0]
        if status == '200 OK':
            body = body.replace(b'<main>', b'<main><aside class="notice"><strong>Demo &middot; Live AI</strong>'
                b' &mdash; Use synthetic data only. Reviews send input to Baseten. '
                b'Orders and uploads can reset after 30 minutes idle or when the service restarts.</aside>', 1)
            body = body.replace(b'<option value="video">', b'<option disabled value="video">')
            headers = [(k, v) for k, v in headers if k.lower() != 'content-length']
            headers.append(('Content-Length', str(len(body))))
            if new_session:
                headers.append(('Set-Cookie', f'__Host-orderthread={session_id}; Secure; HttpOnly; SameSite=Strict; Path=/'))
        start_response(status, headers)
        return [body]


def main():
    from waitress import serve

    os.umask(0o077)
    try:
        origin = os.environ['DEMO_ORIGIN']
        if not re.fullmatch(r'https://[a-z0-9-]+\.onrender\.com', origin):
            raise ValueError('Expected the Render HTTPS origin.')
        budget = PublicAIBudget(os.environ['D1_ACCOUNT_ID'], os.environ['D1_DATABASE_ID'], os.environ['D1_API_TOKEN'])
        model = os.environ['BASETEN_MODEL']
        key = os.environ['BASETEN_API_KEY'].strip()
        if not key or not re.fullmatch(r'[a-zA-Z0-9._/-]{1,120}', model):
            raise ValueError('Baseten credentials and model required.')
        demo = PublicDemo(origin, budget, model, key)
    except (KeyError, ValueError, OSError):
        raise SystemExit('Public demo configuration invalid. Private values withheld.') from None
    serve(demo, host='0.0.0.0', port=int(os.getenv('PORT', '10000')), threads=4,
          connection_limit=20, backlog=20, channel_timeout=75, max_request_body_size=2 * 1024 * 1024)


if __name__ == '__main__':
    main()
