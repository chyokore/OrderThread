"""Temporary mobile browser fixture: real codecs, mocked AI, no persistent data."""
import io,json,tempfile,subprocess
from pathlib import Path
from unittest.mock import patch
import imageio_ffmpeg
from test_audio import app,provider_result
with tempfile.TemporaryDirectory() as folder:
    app.DB=Path(folder)/'browser.db'
    target=Path(folder)/'phone.m4a'
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-f','lavfi','-i','sine=frequency=440:duration=0.5','-c:a','aac',str(target)],check=True,stderr=subprocess.DEVNULL)
    recording=target.read_bytes()
    class Handler(app.Handler):
        def do_GET(self):
            if self.path=='/test-recording': return self.reply(200,recording,'audio/mp4')
            return super().do_GET()
    def provider(request,timeout=60):
        payload=json.loads(request.data)
        assert payload['messages'][1]['content'][1]['audio_url']['url'].startswith('data:audio/wav;base64,')
        return io.BytesIO(json.dumps(provider_result()).encode())
    with patch.dict(app.os.environ,{'AI_PROVIDER':'baseten','BASETEN_API_KEY':'synthetic-only'}),patch.object(app.urllib.request,'urlopen',side_effect=provider):
        print('Temporary mobile audio browser fixture on 8879',flush=True)
        app.ThreadingHTTPServer(('127.0.0.1',8879),Handler).serve_forever()
