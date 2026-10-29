import io,json,tempfile
from pathlib import Path
from unittest.mock import patch
from test_audio import app,provider_result
with tempfile.TemporaryDirectory() as folder:
    app.DB=Path(folder)/'audio-browser.db'
    with patch.dict(app.os.environ,{'BASETEN_API_KEY':'synthetic-test','AI_PROVIDER':'baseten'}),patch.object(app.urllib.request,'urlopen',return_value=io.BytesIO()):
        def provider(request,timeout=60):
            payload=json.loads(request.data)
            assert payload['messages'][1]['content'][1]['type']=='audio_url'
            return io.BytesIO(json.dumps(provider_result()).encode())
        with patch.object(app.urllib.request,'urlopen',side_effect=provider):
            print('Temporary mocked audio server on 8878',flush=True)
            app.ThreadingHTTPServer(('127.0.0.1',8878),app.Handler).serve_forever()
