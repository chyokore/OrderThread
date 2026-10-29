import io,json,tempfile
from pathlib import Path
from unittest.mock import patch
from PIL import Image,ImageDraw
from test_app import app
with tempfile.TemporaryDirectory(prefix='orderthread-catalogue-browser-') as folder:
    folder=Path(folder);app.DB=folder/'browser.db'
    image=Image.new('RGB',(500,160),'white');ImageDraw.Draw(image).text((10,10),'10 blue zips, 20 cm\n2 packs white buttons',fill='black');image.save(folder/'synthetic-order.png')
    (folder/'duplicates.csv').write_text('Product name,Variant,Unit\nZips,Blue,piece\n zips , blue ,PIECE\n',encoding='utf-8')
    (folder/'missing.csv').write_text('Product name,Variant,Unit\n,Blue,piece\n',encoding='utf-8')
    (folder/'invalid.csv').write_bytes(b'\xff\xfeinvalid')
    def provider(request,timeout=60):
        payload=json.loads(request.data);content=payload['messages'][1]['content']
        if isinstance(content,list) and content[1]['type']=='image_url':
            proposal={'items':[{'name':'zips','quantity':10,'variant':'blue, 20 cm','uncertain':False},{'name':'buttons','quantity':2,'variant':'white, packs','uncertain':False}],'intent':'new','clarification':'','fulfillment_note':''}
        else:
            proposal={'items':[{'name':'zips','quantity':10,'variant':'blue, 20 cm','evidence':'10 blue zips'}],'intent':'new','clarification':'','fulfillment_note':''}
        return io.BytesIO(json.dumps({'choices':[{'message':{'content':json.dumps(proposal)}}]}).encode())
    with patch.dict(app.os.environ,{'AI_PROVIDER':'baseten','BASETEN_API_KEY':'synthetic-only'}),patch.object(app.urllib.request,'urlopen',side_effect=provider):
        print('Temporary catalogue fixture on 8883; synthetic files: '+str(folder),flush=True)
        app.ThreadingHTTPServer(('127.0.0.1',8883),app.Handler).serve_forever()
