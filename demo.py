"""Isolated synthetic scenario, real application and real configured AI only."""
import argparse
import importlib.util
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PICKUP = "This is a synthetic demonstration. I have sent the list. I will pick it up tomorrow. Please keep the same quantities."


def prepare(folder):
    from PIL import Image, ImageDraw, ImageFont
    # Bitmap default + scaling also works on the minimum supported Pillow 10.0.
    font = ImageFont.load_default()
    for name, lines in {
        '01-initial-list.png': ['SYNTHETIC DEMO - NO CUSTOMER DATA', 'Initial sewing-materials order', '10 blue zips, 20 cm', '5 red zips, 20 cm'],
        '02-follow-up-list.png': ['SYNTHETIC DEMO - NO CUSTOMER DATA', 'Same blue zips from my first list.', '10 blue zips, 20 cm', 'Also add 2 packs of white buttons.'],
    }.items():
        image = Image.new('RGB', (550, 210), 'white')
        draw = ImageDraw.Draw(image)
        for index, line in enumerate(lines):
            draw.text((15, 18 + index * 42), line, fill='black', font=font)
        image.resize((1100, 420)).save(folder / name)
    (folder / 'pickup-script.txt').write_text('SYNTHETIC DEMO - read this in Voice note mode:\n' + PICKUP + '\n', encoding='utf-8')


def load_app():
    spec = importlib.util.spec_from_file_location('orderthread_demo', ROOT / 'OrderThread' / 'app.py')
    app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app)
    return app


def handler_for(app):
    class DemoHandler(app.Handler):
        def reply(self, status, body, typ='application/json'):
            if typ.startswith('text/html') and isinstance(body, str):
                banner = ('<aside role="note" style="padding:18px;background:#fff4db;border:3px solid #805500">'
                          '<strong>SYNTHETIC JUDGE DEMO — isolated database; LIVE AI requests.</strong> '
                          'No mocked responses or preloaded orders. Compare every proposal with the synthetic source. '
                          'Follow DEMO.md. Provider failures remain errors.</aside>')
                body = body.replace('<main>', '<main>' + banner, 1)
            return super().reply(status, body, typ)
    return DemoHandler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8885)
    parser.add_argument('--prepare-only', action='store_true', help='Generate labelled images/script without starting a server or calling AI.')
    args = parser.parse_args()
    parent = ROOT / '.demo-runs'
    parent.mkdir(exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix='synthetic-', dir=parent))
    prepare(folder)
    print('SYNTHETIC DEMO assets: ' + str(folder), flush=True)
    if args.prepare_only:
        return
    app = load_app()
    app.DB = folder / 'synthetic-demo.db'
    # Bind before accessing the database: a busy port never opens the normal DB.
    try:
        server = app.ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(app))
    except OSError:
        raise SystemExit('Demo port unavailable. Stop the existing demo or choose --port. Existing data was not opened.') from None
    (folder / 'session.json').write_text(json.dumps({'synthetic': True, 'ai_mode': 'live', 'port': server.server_port}), encoding='utf-8')
    print(f'SYNTHETIC DEMO / LIVE AI: http://127.0.0.1:{server.server_port}', flush=True)
    print('Fresh isolated database. No orders are preloaded. Ctrl+C stops; this session is retained locally.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
