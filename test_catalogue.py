import base64,hashlib,json,threading,unittest,urllib.request
from pathlib import Path
from unittest.mock import patch
from test_audio import app,AppTests,wav_audio,provider_result
from test_attachments import AttachmentTests

class CatalogueTests(unittest.TestCase):
    setUp=AppTests.setUp
    tearDown=AppTests.tearDown
    request=AppTests.request
    sample=b'Label,Colour,Pack\r\nZips,"Blue, 20 cm",piece\r\nZips,"Red, 20 cm",piece\r\nButtons,White,pack\r\n'
    def preview(self,content=None):
        status,_,body=self.request('/api/catalogue/preview',{'file':{'name':'synthetic.csv','mime':'text/csv','base64':base64.b64encode(self.sample if content is None else content).decode()}})
        self.assertEqual(status,200,body);return json.loads(body)
    def mapped(self,draft,mapping=None):
        status,_,body=self.request('/api/catalogue/map',{'draft_id':draft['draft_id'],'mapping':mapping or {'name':0,'variant':1,'unit':2}})
        self.assertEqual(status,200,body);return json.loads(body)
    def payload(self,draft,review,submission='import-1'):
        return {'draft_id':draft['draft_id'],'review_id':review['review_id'],'submission_id':submission,'confirmed':True}
    def products(self,query=''):
        from urllib.parse import quote
        return json.loads(self.request('/api/catalogue?q='+quote(query))[2])
    def imported(self):
        draft=self.preview();review=self.mapped(draft);payload=self.payload(draft,review);self.assertEqual(self.request('/api/catalogue/import',payload)[0],200);return self.products()['products']

    def test_preview_mapping_confirmation_import_and_search(self):
        draft=self.preview();self.assertEqual(draft['row_count'],3);self.assertEqual(self.products()['total'],0);self.assertEqual(app.events(),[])
        # Explicit mapping from reordered, non-default headers.
        reordered=self.preview(b'Unit,Description,Shade\npack,Buttons,White\n')
        review=self.mapped(reordered,{'name':1,'variant':2,'unit':0});self.assertEqual(review['rows'][0]['name'],'Buttons')
        payload=self.payload(reordered,review);payload['confirmed']=False
        self.assertEqual(self.request('/api/catalogue/import',payload)[0],400);self.assertEqual(self.products()['total'],0)
        payload['confirmed']=True;self.assertEqual(self.request('/api/catalogue/import',payload)[0],200)
        found=self.products('white pack');self.assertEqual(found['total'],1);self.assertEqual(found['products'][0]['unit'],'pack')
        with app.db() as c:
            audit=c.execute('SELECT source_sha256,mapping,row_count FROM catalogue_imports').fetchone()
            self.assertEqual(audit['row_count'],1);self.assertEqual(json.loads(audit['mapping']),{'name':1,'variant':2,'unit':0})
        self.assertEqual(app.events(),[]);self.assertEqual(app.orders(),[])

    def test_invalid_files_and_mapping_cannot_write(self):
        files=[('bad.xlsx',b'PKbinary'),('bad.csv',b'\xff\xfeinvalid'),('bad.csv',b'Name\nBad\x00value'),('bad.csv',b'Name,Variant\n"unfinished'),('bad.csv',b'Name,Variant\nZips,Blue,Extra\n'),('bad.csv',b'Name,name\nZips,Blue\n'),('bad.csv',b'Name;Variant;Unit\nZips;Blue;piece\n'),('bad.csv',b'\n'),('bad.csv',b'Name\n'),('bad.csv',b'Name\n'+b'A'*501),('bad.csv',b'Name\n'+b'Zips\n'*1001),('bad.csv',b'x'*(app.MAX_CATALOGUE_BYTES+1))]
        for name,content in files:
            with self.subTest(name=name,bytes=len(content)):
                self.assertEqual(self.request('/api/catalogue/preview',{'file':{'name':name,'base64':base64.b64encode(content).decode()}})[0],400)
        self.assertEqual(self.request('/api/catalogue/preview',{'file':{'name':'bad.csv','base64':'!'}})[0],400)
        draft=self.preview()
        for mapping in ({'name':None,'variant':1,'unit':2},{'name':True,'variant':1,'unit':2},{'name':3,'variant':1,'unit':2},{'name':0,'variant':0,'unit':None},{}):
            self.assertEqual(self.request('/api/catalogue/map',{'draft_id':draft['draft_id'],'mapping':mapping})[0],400)
        self.assertEqual(self.products()['total'],0)

    def test_missing_names_duplicates_and_existing_duplicates_are_atomic(self):
        for content in (b'Name,Variant,Unit\n,Blue,piece\nButtons,White,pack\n',b'Name,Variant,Unit\nZips,Blue,piece\n zips , blue , PIECE\n'):
            draft=self.preview(content);review=self.mapped(draft);self.assertGreater(review['error_count'],0)
            self.assertEqual(self.request('/api/catalogue/import',self.payload(draft,review))[0],400);self.assertEqual(self.products()['total'],0)
        self.imported();draft=self.preview();review=self.mapped(draft);self.assertEqual(review['error_count'],3)
        self.assertTrue(all('already in the local catalogue' in ' '.join(row['errors']) for row in review['rows']))
        self.assertEqual(self.request('/api/catalogue/import',self.payload(draft,review,'duplicates'))[0],400);self.assertEqual(self.products()['total'],3)

    def test_stale_mapping_expiry_and_catalogue_changes(self):
        draft=self.preview();old=self.mapped(draft);new=self.mapped(draft)
        self.assertEqual(self.request('/api/catalogue/import',self.payload(draft,old))[0],400)
        with patch.object(app.time,'monotonic',return_value=app.time.monotonic()+1801): self.assertEqual(self.request('/api/catalogue/import',self.payload(draft,new))[0],400)
        other=self.preview();mapped=self.mapped(other);self.assertEqual(self.request('/api/catalogue/import',self.payload(other,mapped,'other'))[0],200)
        self.assertEqual(self.request('/api/catalogue/import',self.payload(draft,new))[0],400);self.assertEqual(self.products()['total'],3)
        self.assertEqual(self.request('/api/catalogue/import',{'draft_id':'forged','review_id':'forged','confirmed':True,'submission_id':'forged'})[0],400)

    def test_restart_and_repeated_submissions(self):
        draft=self.preview();review=self.mapped(draft);payload=self.payload(draft,review)
        self.assertEqual(self.request('/api/catalogue/import',payload)[0],200);before=self.products()
        self.assertNotIn(draft['draft_id'],app.CATALOGUE_DRAFTS)
        self.server.shutdown();self.server.server_close();self.thread.join();app.CATALOGUE_DRAFTS.clear()
        self.server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.base='http://127.0.0.1:'+str(self.server.server_port)
        self.assertEqual(self.products(),before)
        status,_,body=self.request('/api/catalogue/import',payload);self.assertEqual(status,200);self.assertTrue(json.loads(body)['already_imported'])
        payload['review_id']='changed';self.assertEqual(self.request('/api/catalogue/import',payload)[0],400)
        with app.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM catalogue_imports').fetchone()[0],1)

    def test_concurrent_imports_recheck_duplicates(self):
        first=self.preview();a=self.mapped(first);second=self.preview();b=self.mapped(second);results=[]
        requests=[self.payload(first,a,'race-a'),self.payload(second,b,'race-b')]
        threads=[threading.Thread(target=lambda data=data:results.append(self.request('/api/catalogue/import',data)[0])) for data in requests]
        for thread in threads:thread.start()
        for thread in threads:thread.join()
        self.assertEqual(sorted(results),[200,400]);self.assertEqual(self.products()['total'],3)

    def test_optional_columns_utf8_and_literal_markup(self):
        draft=self.preview('\ufeffLabel,Extra\nÀwọ̀ búlúù,info\n<img src=x onerror=alert(1)>,info\n'.encode())
        review=self.mapped(draft,{'name':0,'variant':None,'unit':None});self.assertEqual(review['error_count'],0)
        self.assertEqual(self.request('/api/catalogue/import',self.payload(draft,review))[0],200)
        self.assertEqual(self.products('Àwọ̀')['total'],1);self.assertEqual(self.products('<img')['products'][0]['unit'],'')

    def test_matching_selection_and_ignore_never_change_items_or_quantities(self):
        products=self.imported();blue=next(p for p in products if p['variant']=='Blue, 20 cm')
        status,_,body=self.request('/api/catalogue/matches',{'items':[{'name':'zip','variant':'BLUE 20cm'},{'name':'unrelated','variant':None},{'name':None,'variant':None}]})
        self.assertEqual(status,200);matches=json.loads(body)['matches'];self.assertEqual(matches[0][0]['id'],blue['id']);self.assertEqual(matches[1:], [[],[]])
        self.assertTrue(all('stock' not in p and 'quantity' not in p for p in matches[0]));self.assertEqual(app.events(),[])
        for choice,expected in ((blue['id'],'reference'),('ignore','ignored'),(None,'none')):
            payload={'message':'10 blue zips','proposal':{'items':[{'name':'zips','quantity':10,'variant':'blue, 20 cm','evidence':'10 blue zips'}]},'decisions':['new'],'catalogue_choices':[choice]}
            status,_,body=self.request('/api/confirm',payload);self.assertEqual(status,200,body)
            saved=next(e['data']['items'][0] for e in app.events() if e['id']==json.loads(body)['event_id'])
            self.assertEqual((saved['name'],saved['variant'],saved['quantity']),('zips','blue, 20 cm',10));self.assertNotIn('unit',saved)
            if expected=='reference':self.assertEqual(saved['catalogue_reference']['id'],blue['id'])
            if expected=='ignored':self.assertTrue(saved['catalogue_ignored'])
        before=len(app.events());payload['catalogue_choices']=['forged'];self.assertEqual(self.request('/api/confirm',payload)[0],400);self.assertEqual(len(app.events()),before)
        self.assertEqual(app.orders(),[])

    def test_extra_stock_and_quantity_columns_are_not_interpreted(self):
        draft=self.preview(b'Name,Variant,Unit,Stock,Order quantity\nWidgets,Small,piece,999,400\n')
        review=self.mapped(draft);self.assertEqual(self.request('/api/catalogue/import',self.payload(draft,review))[0],200)
        product=self.products()['products'][0]
        self.assertEqual((product['name'],product['variant'],product['unit']),('Widgets','Small','piece'))
        self.assertNotIn('stock',product);self.assertNotIn('quantity',product);self.assertNotIn('available',product)
        self.assertEqual(app.orders(),[]);self.assertEqual(app.events(),[])

    def test_image_and_audio_reference_provenance(self):
        blue=next(p for p in self.imported() if p['variant']=='Blue, 20 cm')
        image_event=AttachmentTests.image_review(self)
        # Confirmed image is immutable; independently review the same image draft for an explicit catalogue choice.
        source=next(e['data'] for e in app.events() if e['id']==image_event)['source_id']
        token=next(token for token,draft in app.IMAGE_DRAFTS.items() if draft['proposal']['source_id']==source)
        proposal=app.IMAGE_DRAFTS[token]['proposal']
        payload={'image_draft_id':token,'image_reviewed':True,'proposal':proposal,'decisions':['new','new'],'catalogue_choices':[blue['id'],'ignore']}
        status,_,body=self.request('/api/confirm',payload);self.assertEqual(status,200,body);image_id=json.loads(body)['event_id']
        record=next(e['data'] for e in app.events() if e['id']==image_id);self.assertEqual(record['source_id'],source);self.assertEqual([i['quantity'] for i in record['items']],[10,5]);self.assertEqual(record['items'][0]['catalogue_reference']['id'],blue['id']);self.assertEqual(record['extracted_proposal']['items'][0]['quantity'],10)
        response=provider_result([{'name':'zips','quantity':2,'variant':'blue, 20 cm','uncertain':False}])
        with patch.object(app,'ai_completion',return_value=(response,{'provider':'baseten','model':app.MODEL})): proposal=app.propose_audio(wav_audio(),'baseten')
        status,_,body=self.request('/api/confirm',{'audio_draft_id':proposal['audio_draft_id'],'audio_reviewed':True,'proposal':proposal,'decisions':['new'],'submission_id':'audio-catalogue','catalogue_choices':[blue['id']]})
        self.assertEqual(status,200,body);record=next(e['data'] for e in app.events() if e['id']==json.loads(body)['event_id']);self.assertEqual(record['source_type'],'audio');self.assertEqual(record['items'][0]['quantity'],2);self.assertEqual(record['items'][0]['catalogue_reference']['id'],blue['id'])
        status,_,body=self.request('/api/apply',{'event_id':image_id,'order_id':'__new__','order_name':'Catalogue reference test','targets':[None,None],'confirmed':True});self.assertEqual(status,200,body)
        order=app.orders()[0];before=order['items'];line=before[0]['id']
        for kind,quantity in (('dispatch',4),('receipt',2)):
            self.assertEqual(self.request('/api/fulfillment',{'order_id':order['id'],'kind':kind,'items':[{'line_id':line,'quantity':quantity}],'submission_id':kind,'confirmed':True})[0],200)
        before=app.orders();events=app.events();draft=self.preview(b'Name,Variant,Unit\nNew product,Small,piece\n');review=self.mapped(draft);self.assertEqual(self.request('/api/catalogue/import',self.payload(draft,review,'append'))[0],200)
        self.assertEqual(app.orders(),before);self.assertEqual(app.events(),events)

if __name__=='__main__':unittest.main()
