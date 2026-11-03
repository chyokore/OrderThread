"""Bounded shared synthetic demo. Run only behind the host's HTTPS edge."""
import base64
import hashlib
import hmac
import importlib.util
import io
import json
import os
import threading
import time
from email.message import Message
from http import HTTPStatus
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
MAX_BODY = 28 * 1024 * 1024
FIXTURES = {
    'SYNTHETIC: 10 blue zips': {'items': [{'name': 'zips', 'variant': 'blue', 'quantity': 10, 'evidence': '10 blue zips'}], 'intent': 'new', 'clarification': '', 'fulfillment_note': ''},
    'SYNTHETIC: add 5 blue zips': {'items': [{'name': 'zips', 'variant': 'blue', 'quantity': 5, 'evidence': '5 blue zips'}], 'intent': 'add', 'clarification': '', 'fulfillment_note': ''},
}
AI_PATHS = {'/api/propose', '/api/propose-image', '/api/propose-audio'}


class HostedDemo:
    def __init__(self, data_dir, origin, password, ai_budget=None):
        parsed = urlsplit(origin)
        if parsed.scheme != 'https' or not parsed.netloc or parsed.path or parsed.query or parsed.fragment or parsed.username:
            raise ValueError('DEMO_ORIGIN must be an HTTPS origin without a trailing slash.')
        if len(password) < 24:
            raise ValueError('DEMO_PASSWORD must contain at least 24 characters.')
        if not Path(data_dir).is_absolute():
            raise ValueError('Hosted storage must use an absolute disposable-data path.')
        directory = Path(data_dir).resolve()
        if directory == ROOT or ROOT in directory.parents:
            raise ValueError('Hosted storage must be outside the source checkout.')
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        marker = directory / 'SYNTHETIC_ONLY'
        if not marker.exists() and any(directory.iterdir()):
            raise ValueError('Hosted storage must be empty or marked SYNTHETIC_ONLY.')
        if marker.exists() and not marker.is_file():
            raise ValueError('Hosted storage marker must be a file.')
        for name in ('synthetic-demo.db', 'budget.sqlite', 'SYNTHETIC_ONLY'):
            if (directory / name).is_symlink():
                raise ValueError('Hosted data files must not be symbolic links.')
        marker.touch()
        self.origin, self.password = origin, password
        self.lock = threading.Lock()
        self.window, self.requests = time.monotonic(), 0
        self.directory = directory
        # Reject the obsolete disk-backed allowance rather than imply persistence.
        if ai_budget is not None:
            raise ValueError('DEMO_AI_BUDGET is unsupported on free hosting; live AI is disabled.')
        # Do not read the presenter's local configuration, even during local tests.
        previous = os.environ.get('ORDERTHREAD_HOSTED')
        os.environ['ORDERTHREAD_HOSTED'] = '1'
        spec = importlib.util.spec_from_file_location('hosted_orderthread', ROOT / 'OrderThread' / 'app.py')
        self.app = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(self.app)
        finally:
            if previous is None:
                os.environ.pop('ORDERTHREAD_HOSTED', None)
            else:
                os.environ['ORDERTHREAD_HOSTED'] = previous
        self.app.DB = directory / 'synthetic-demo.db'
        original_db = self.app.db
        from contextlib import contextmanager

        @contextmanager
        def bounded_db():
            with original_db() as connection:
                # 256 MiB ceiling, including confirmed media. Reserve disk space for journals.
                page_size = connection.execute('PRAGMA page_size').fetchone()[0]
                connection.execute('PRAGMA max_page_count=' + str(256 * 1024 * 1024 // page_size))
                yield connection
        self.app.db = bounded_db
        # Fail startup before reporting healthy if schema storage is unwritable.
        with self.app.db():
            pass
        def fixture_completion(messages, provider=None):
            # No path to the original provider function: restart-safe $0 inference.
            # Match only text requests with one of the published synthetic scripts.
            try:
                payload = json.loads(messages[-1]['content'])
                message = payload['new_message']
                proposal = FIXTURES[message]
            except (KeyError, TypeError, ValueError, IndexError):
                raise self.app.ProviderError('Live AI disabled. Use a published synthetic text fixture.') from None
            return {'choices': [{'message': {'content': json.dumps(proposal)}}]}, {
                'provider': 'synthetic-fixture', 'model': 'fixed-script-no-live-ai'}
        self.app.ai_completion = fixture_completion
        self.app.provider_status = lambda: {
            'configured': True, 'default_provider': 'baseten',
            'providers': [{'id': 'baseten', 'name': 'Synthetic fixtures (NO LIVE AI)',
                           'configured': True, 'model': 'fixed-script-no-live-ai',
                           'input_modalities': ['text'], 'output_modalities': ['text'],
                           'capability_basis': 'Fixed published scripts, not AI extraction.'}],
            'error': None}

    def __call__(self, env, start_response):
        def respond(code, message, extra=()):
            body = json.dumps({'error': message}).encode()
            start_response(f'{code} {HTTPStatus(code).phrase}', self.security_headers() + [
                ('Content-Type', 'application/json'), ('Content-Length', str(len(body))), *extra])
            return [body]
        path = env.get('PATH_INFO', '/')
        method = env.get('REQUEST_METHOD', 'GET')
        if path == '/healthz' and method == 'GET':
            start_response('200 OK', [('Content-Type', 'text/plain'), ('Content-Length', '2')])
            return [b'OK']
        if env.get('HTTP_HOST') != urlsplit(self.origin).netloc:
            return respond(400, 'Unexpected host.')
        expected = 'Basic ' + base64.b64encode(('judge:' + self.password).encode()).decode()
        if not hmac.compare_digest(hashlib.sha256(env.get('HTTP_AUTHORIZATION', '').encode()).digest(),
                                   hashlib.sha256(expected.encode()).digest()):
            return respond(401, 'Judge access required.', [('WWW-Authenticate', 'Basic realm="Synthetic OrderThread", charset="UTF-8"')])
        if method not in ('GET', 'POST'):
            return respond(405, 'Method not allowed.', [('Allow', 'GET, POST')])
        if len(path) + len(env.get('QUERY_STRING', '')) > 2048:
            return respond(414, 'Request target too long.')
        if method == 'POST':
            if env.get('HTTP_ORIGIN') != self.origin or env.get('HTTP_SEC_FETCH_SITE') == 'cross-site':
                return respond(403, 'Use the demo page to submit changes.')
            if env.get('CONTENT_TYPE', '').split(';')[0].lower() != 'application/json':
                return respond(415, 'Expected application/json.')
            try:
                size = int(env.get('CONTENT_LENGTH', ''))
            except ValueError:
                return respond(411, 'Content length required.')
            limit = MAX_BODY if path == '/api/video-preview' else self.app.MAX_IMAGE_REQUEST if path in AI_PATHS - {'/api/propose'} else 355000 if path == '/api/catalogue/preview' else 50000
            if size < 1 or size > limit:
                return respond(413, 'Upload or request exceeds the demo limit.')
        # One active request keeps draft/ledger operations bounded; no unbounded app queue.
        if not self.lock.acquire(timeout=3 if method == 'GET' else 0):
            return respond(503, 'Demo busy. Wait, then refresh before retrying a change.', [('Retry-After', '3')])
        try:
            now = time.monotonic()
            if now - self.window >= 60:
                self.window, self.requests = now, 0
            self.requests += 1
            if self.requests > 120:
                return respond(429, 'Shared demo request limit reached. Wait one minute.', [('Retry-After', '60')])
            for drafts in (self.app.IMAGE_DRAFTS, self.app.AUDIO_DRAFTS, self.app.VIDEO_DRAFTS, self.app.CATALOGUE_DRAFTS):
                for token in list(drafts):
                    if time.monotonic() - drafts[token]['created'] > 1800:
                        del drafts[token]
            return self.dispatch(env, start_response)
        except Exception:
            # Never log submitted content, authorization, exception text or provider bodies.
            return respond(500, 'Demo request failed. Refresh and contact the presenter if it persists.')
        finally:
            self.lock.release()

    @staticmethod
    def security_headers():
        return [('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'),
                ('X-Frame-Options', 'DENY'), ('Referrer-Policy', 'no-referrer'),
                ('Strict-Transport-Security', 'max-age=31536000'),
                ('Permissions-Policy', 'microphone=(self), camera=()'),
                ('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")]

    def dispatch(self, env, start_response):
        outer = self
        class Adapter(self.app.Handler):
            def send_response(self, code, message=None):
                self.status = code
                self.response_headers = []
            def send_header(self, name, value):
                self.response_headers.append((name, str(value)))
            def end_headers(self):
                pass
            def log_message(self, *args):
                pass
            def reply(self, status, body, typ='application/json; charset=utf-8'):
                if status >= 500:
                    body = {'error': 'Demo service unavailable. Check with the presenter; no automatic retry was made.'}
                if typ.startswith('text/html'):
                    body = body.replace('<main>', '<main><aside role="note" class="notice"><strong>SHARED SYNTHETIC DEMO / NO LIVE AI</strong> — Invented data only. Judges share this workspace; another judge may change it. Human confirmation is required. Orders and uploaded media stored locally can be lost on restart, redeploy or idle spin-down. Recreate with: SYNTHETIC: 10 blue zips; then SYNTHETIC: add 5 blue zips. These are fixed text fixtures, not AI extraction. Image/audio AI is disabled.</aside>', 1)
                    body = body.replace('1. Add text, an image, a voice note or selected video frames', '1. Review a synthetic text script')
                    body = body.replace('Use synthetic or anonymised sources. Text, uploaded images or separately supplied audio are sent to the selected AI provider for extraction. In Video frame review, only the selected still image is sent. Text requests also include confirmed history.', 'Use only the two published synthetic scripts. Proposals are fixed fixtures; no source or history is sent to an AI provider.')
                    body = body.replace('AI provider for this extraction', 'Demo proposal source')
                    body = body.replace('Please send 10 blue zips, size 20cm.', 'SYNTHETIC: 10 blue zips')
                    body = body.replace('AI configured. ', 'Fixed scripts enabled. ')
                    body = body.replace("(provider.id==='baseten'?'Text, image and voice-note audio':'Text and image')", "'Published synthetic text scripts only'")
                    body = body.replace('Account model access has not been live-verified.', 'No provider requests are made.')
                    # Keep media validation in the server, but avoid presenting disabled AI flows.
                    body = body.replace('<option value="image">', '<option disabled value="image">')
                    body = body.replace('<option value="audio">', '<option disabled value="audio">')
                    body = body.replace('<option value="video">', '<option disabled value="video">')
                    body = body.replace('Decisions saved on this computer.', 'Disposable synthetic decisions; may be lost on restart.')
                    body = body.replace('saving its original video locally', 'saving its original video on the demo server')
                super().reply(status, body, typ)
        handler = Adapter.__new__(Adapter)
        handler.path = env.get('PATH_INFO', '/') + ('?' + env['QUERY_STRING'] if env.get('QUERY_STRING') else '')
        handler.headers = Message()
        for key, value in env.items():
            if key.startswith('HTTP_'):
                handler.headers[key[5:].replace('_', '-')] = value
        handler.headers['Content-Length'] = env.get('CONTENT_LENGTH', '0')
        handler.rfile = env['wsgi.input']
        handler.wfile = io.BytesIO()
        if env['REQUEST_METHOD'] == 'POST':
            handler.do_POST()
        else:
            handler.do_GET()
        headers = [(k, v) for k, v in handler.response_headers if k.lower() not in {'cache-control', 'x-content-type-options'}]
        start_response(f'{handler.status} {HTTPStatus(handler.status).phrase}', headers + outer.security_headers())
        return [handler.wfile.getvalue()]


def main():
    # Disposable SQLite files and journals should be private on Linux.
    os.umask(0o077)
    from waitress import serve
    try:
        demo = HostedDemo(os.getenv('DEMO_DATA_DIR', '/tmp/orderthread-synthetic'), os.environ['DEMO_ORIGIN'],
                          os.environ['DEMO_PASSWORD'], os.getenv('DEMO_AI_BUDGET'))
    except Exception:
        raise SystemExit('Hosted configuration invalid. Check private environment settings and dedicated storage; values withheld.') from None
    serve(demo, host='0.0.0.0', port=int(os.getenv('PORT', '10000')), threads=4,
          connection_limit=24, backlog=24, channel_timeout=90, cleanup_interval=5,
          max_request_header_size=16384, max_request_body_size=MAX_BODY,
          expose_tracebacks=False, clear_untrusted_proxy_headers=True)


if __name__ == '__main__':
    main()
