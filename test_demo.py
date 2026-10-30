"""Synthetic launcher safety checks; no live AI or normal database writes."""
import tempfile
import unittest
import urllib.request
import subprocess
import sys
import json
from pathlib import Path
from unittest.mock import patch
import demo
from evaluate import Fixture, new_record


class DemoTests(unittest.TestCase):
    def test_real_launcher_serves_isolated_session(self):
        # Run the actual entry point; GET requests never invoke a provider.
        process = subprocess.Popen([sys.executable, '-u', str(demo.ROOT / 'demo.py'), '--port', '0'],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            # communicate cannot be used while serving; bounded request/startup handled by a reader future.
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                startup = pool.submit(lambda: [process.stdout.readline(), process.stdout.readline()])
                try:
                    lines = startup.result(timeout=15)
                except concurrent.futures.TimeoutError:
                    process.terminate()
                    raise AssertionError('Demo launcher did not become ready') from None
            self.assertTrue(lines[0].startswith('SYNTHETIC DEMO assets: '))
            url = lines[1].strip().split('LIVE AI: ')[1]
            with urllib.request.urlopen(url, timeout=5) as response:
                self.assertIn('SYNTHETIC JUDGE DEMO', response.read().decode())
            with urllib.request.urlopen(url + '/api/orders', timeout=5) as response:
                self.assertEqual(json.load(response), [])
        finally:
            process.terminate()
            process.communicate(timeout=10)

    def test_generated_lists_are_labelled_and_voice_is_a_script(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            demo.prepare(root)
            self.assertEqual({p.name for p in root.iterdir()},
                             {'01-initial-list.png', '02-follow-up-list.png', 'pickup-script.txt'})
            self.assertIn('synthetic demonstration', (root / 'pickup-script.txt').read_text())
            from PIL import Image
            for name in ('01-initial-list.png', '02-follow-up-list.png'):
                with Image.open(root / name) as image:
                    self.assertEqual(image.size, (1100, 420))

    def test_banner_and_fresh_database_with_real_handler(self):
        with Fixture() as fixture:
            fixture.server.RequestHandlerClass = demo.handler_for(fixture.app)
            with urllib.request.urlopen(f'http://127.0.0.1:{fixture.server.server_port}/', timeout=5) as response:
                html = response.read().decode()
            self.assertIn('SYNTHETIC JUDGE DEMO', html)
            self.assertIn('LIVE AI requests', html)
            self.assertEqual(fixture.ok('/api/orders'), [])
            self.assertNotEqual(fixture.app.DB, demo.ROOT / 'OrderThread' / 'orderthread.db')

    def test_new_live_record_contains_no_invented_observations(self):
        record = new_record('live-ai')
        self.assertEqual(len(record['cases']), 8)
        for row in record['cases']:
            self.assertEqual(row['outcome'], 'not-run')
            self.assertIsNone(row['observed'])
            self.assertIsNone(row['raw_proposal'])
            self.assertIsNone(row['missed_overlap_indexes'])
            self.assertIsNone(row['false_warning_indexes'])

    def test_busy_port_never_serves_or_opens_normal_database(self):
        with tempfile.TemporaryDirectory() as folder:
            app = demo.load_app()
            with patch.object(demo, 'ROOT', Path(folder)), patch.object(demo, 'load_app', return_value=app), \
                 patch.object(app, 'ThreadingHTTPServer', side_effect=OSError()), \
                 patch('sys.argv', ['demo.py']):
                with self.assertRaisesRegex(SystemExit, 'Demo port unavailable'):
                    demo.main()
            self.assertNotEqual(app.DB, demo.ROOT / 'OrderThread' / 'orderthread.db')
            self.assertFalse(app.DB.exists())


if __name__ == '__main__':
    unittest.main()
