"""Synthetic saved image reviews and temporary order for overlap browser tests."""
import base64,hashlib,io,json,tempfile
from pathlib import Path
from PIL import Image,ImageDraw
from test_audio import app
with tempfile.TemporaryDirectory() as folder:
    app.DB=Path(folder)/'browser.db'
    zips={'name':'zips','quantity':10,'variant':'blue, 20 cm','decision':'new','source_type':'image','human_verified':True}
    def save(items):
        picture=Image.new('RGB',(450,150),'white');ImageDraw.Draw(picture).text((10,10),'\n'.join(str(i['quantity'])+' '+i['variant']+' '+i['name'] for i in items),fill='black');buffer=io.BytesIO();picture.save(buffer,format='PNG');content=buffer.getvalue();source=hashlib.sha256(content).hexdigest()
        record={'review_version':2,'source_type':'image','source_id':source,'message':'Order-list image','items':[dict(i,source_id=source) for i in items],'fulfillment_note':'','clarification':''}
        with app.db() as c:
            c.execute('INSERT OR IGNORE INTO source_images VALUES (?,?,?)',(source,'image/png',content))
            return c.execute('INSERT INTO events(kind,data) VALUES (?,?)',('confirmed_proposal',json.dumps(record))).lastrowid
    first=save([zips]);order=app.apply_review({'event_id':first,'order_id':'__new__','order_name':'Overlap browser order','targets':[None],'confirmed':True})['order_id']
    later=save([dict(zips,decision='add'),{'name':'buttons','quantity':2,'variant':'white, packs','decision':'new','source_type':'image','human_verified':True}])
    stale=save([dict(zips,quantity=3,decision='add')])
    print('Temporary overlap browser fixture on 8881; saved synthetic image reviews, no AI',flush=True)
    app.ThreadingHTTPServer(('127.0.0.1',8881),app.Handler).serve_forever()
