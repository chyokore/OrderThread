"""Simulate a missing recorder asset with a temporary, empty database."""
from pathlib import Path
import tempfile
from test_app import app
class Handler(app.Handler):
    def do_GET(self):
        if self.path=='/recorder.js':return self.reply(404,{'error':'Missing test asset'})
        return super().do_GET()
with tempfile.TemporaryDirectory() as folder:
    app.DB=Path(folder)/'startup.db'
    print('Temporary missing-recorder startup fixture on 8882',flush=True)
    app.ThreadingHTTPServer(('127.0.0.1',8882),Handler).serve_forever()
