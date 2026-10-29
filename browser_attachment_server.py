"""Synthetic image + voice-note attachment browser fixture; no real AI/data."""
import base64,io,json,tempfile
from pathlib import Path
from unittest.mock import patch
from PIL import Image,ImageDraw
from test_audio import app
with tempfile.TemporaryDirectory() as folder:
    app.DB=Path(folder)/'browser.db'
    image=Image.new('RGB',(400,120),'white');ImageDraw.Draw(image).text((10,10),'10 blue zips\n5 red zips',fill='black');buffer=io.BytesIO();image.save(buffer,format='PNG');png=buffer.getvalue()
    class Handler(app.Handler):
        def do_GET(self):
            if self.path=='/test-image': return self.reply(200,png,'image/png')
            return super().do_GET()
    def provider(request,timeout=60):
        payload=json.loads(request.data);content=payload['messages'][1]['content']
        if isinstance(content,list) and content[1]['type']=='image_url':
            proposal={'items':[{'name':'zips','quantity':10,'variant':'blue','uncertain':False},{'name':'zips','quantity':5,'variant':'red','uncertain':False}],'intent':'new','clarification':'','fulfillment_note':''}
        elif isinstance(content,list) and content[1]['type']=='audio_url':
            proposal={'items':[],'transcript':'The buyer will pick it up tomorrow.','intent':'unclear','clarification':'','fulfillment_note':'Buyer will pick it up tomorrow.'}
        else: raise ValueError('Only synthetic image/audio requests are expected.')
        return io.BytesIO(json.dumps({'choices':[{'message':{'content':json.dumps(proposal)}}]}).encode())
    with patch.dict(app.os.environ,{'AI_PROVIDER':'baseten','BASETEN_API_KEY':'synthetic-only'}),patch.object(app.urllib.request,'urlopen',side_effect=provider):
        print('Temporary attachment browser fixture on 8880',flush=True)
        app.ThreadingHTTPServer(('127.0.0.1',8880),Handler).serve_forever()
