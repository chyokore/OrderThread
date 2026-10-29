import base64,io,json,unittest
from unittest.mock import patch
from PIL import Image,ImageDraw
from test_audio import app,AppTests

class OverlapTests(unittest.TestCase):
    setUp=AppTests.setUp
    tearDown=AppTests.tearDown
    request=AppTests.request

    def review(self,items,decisions):
        picture=Image.new('RGB',(450,150),'white');ImageDraw.Draw(picture).text((10,10),'10 blue zips, 20 cm\n2 packs white buttons',fill='black');buffer=io.BytesIO();picture.save(buffer,format='PNG')
        response={'items':[dict(i,uncertain=False) for i in items],'intent':'unclear','clarification':'','fulfillment_note':''}
        with patch.object(app,'ai_completion',return_value=({'choices':[{'message':{'content':json.dumps(response)}}]}, {'provider':'baseten','model':app.MODEL})):
            status,_,body=self.request('/api/propose-image',{'image':{'mime':'image/png','base64':base64.b64encode(buffer.getvalue()).decode()},'provider':'baseten'})
        self.assertEqual(status,200);proposal=json.loads(body)
        status,_,body=self.request('/api/confirm',{'proposal':proposal,'image_draft_id':proposal['image_draft_id'],'image_reviewed':True,'decisions':decisions})
        self.assertEqual(status,200,body);return json.loads(body)['event_id']

    def zips(self,quantity=10,variant='blue, 20 cm'): return {'name':'zips','quantity':quantity,'variant':variant}
    def buttons(self): return {'name':'buttons','quantity':2,'variant':'white, packs'}
    def initial(self):
        event=self.review([self.zips()],['new']);status,_,body=self.request('/api/apply',{'event_id':event,'order_id':'__new__','order_name':'Overlap order','targets':[None],'confirmed':True});self.assertEqual(status,200);return json.loads(body)['order_id']
    def preview(self,event,order):
        status,_,body=self.request('/api/apply-preview',{'event_id':event,'order_id':order});self.assertEqual(status,200,body);return json.loads(body)
    def payload(self,event,order,preview,decision,targets):return {'event_id':event,'order_id':order,'order_state':preview['state_token'],'overlap_resolutions':{'0':decision},'targets':targets,'confirmed':True}

    def test_image_repeat_and_independent_white_buttons(self):
        order=self.initial();event=self.review([self.zips(),self.buttons()],['add','new']);preview=self.preview(event,order)
        self.assertEqual([m['index'] for m in preview['overlaps']],[0]);self.assertEqual(preview['overlaps'][0]['existing'][0]['quantity'],10)
        original=next(e['data'] for e in app.events() if e['id']==event)
        missing={'event_id':event,'order_id':order,'targets':['__new__',None],'confirmed':True}
        self.assertEqual(self.request('/api/apply',missing)[0],400)
        missing.update(order_state=preview['state_token']);self.assertEqual(self.request('/api/apply',missing)[0],400)
        self.assertEqual(len(app.orders()[0]['items']),1)
        payload=self.payload(event,order,preview,'repeat',[None,None]);self.assertEqual(self.request('/api/apply',payload)[0],200)
        self.assertEqual([(i['name'],i['quantity']) for i in app.orders()[0]['items']],[('zips',10),('buttons',2)])
        self.assertEqual(next(e['data'] for e in app.events() if e['id']==event),original)
        audit=app.events()[-1]['data'];self.assertEqual(audit['items'][0]['decision'],'repeat');self.assertEqual(audit['saved_items'][0]['decision'],'add');self.assertEqual(audit['source_type'],'image')
        self.assertEqual(self.request('/api/apply',payload)[0],200);self.assertEqual(app.orders()[0]['items'][0]['quantity'],10)
        payload['overlap_resolutions']['0']='add';self.assertEqual(self.request('/api/apply',payload)[0],400)

    def test_intentional_addition_and_replacement(self):
        order=self.initial();line=app.orders()[0]['items'][0]['id'];event=self.review([self.zips()],['add']);preview=self.preview(event,order)
        self.assertEqual(self.request('/api/apply',self.payload(event,order,preview,'add',[line]))[0],200);self.assertEqual(app.orders()[0]['items'][0]['quantity'],20)
        event=self.review([self.zips(1,'BLUE 20cm')],['add']);preview=self.preview(event,order)
        self.assertEqual(self.request('/api/apply',self.payload(event,order,preview,'add',[line]))[0],200);self.assertEqual(app.orders()[0]['items'][0]['quantity'],21)
        event=self.review([self.zips(7)],['add']);preview=self.preview(event,order)
        self.assertEqual(self.request('/api/apply',self.payload(event,order,preview,'replace',[line]))[0],200);self.assertEqual(app.orders()[0]['items'][0]['quantity'],7)

    def test_variants_normalization_and_incomplete_details(self):
        order=self.initial()
        for variant,expected in [('red, 20 cm',False),('blue, 30 cm',False),('BLUE 20cm',True),('blue',True),(None,True)]:
            event=self.review([self.zips(10,variant)],['new']);preview=self.preview(event,order)
            self.assertEqual(bool(preview['overlaps']),expected,variant)
        event=self.review([self.zips(3,'red, 20 cm')],['new']);preview=self.preview(event,order)
        self.assertEqual(self.request('/api/apply',{'event_id':event,'order_id':order,'order_state':preview['state_token'],'overlap_resolutions':{},'targets':[None],'confirmed':True})[0],200)
        self.assertEqual(len(app.orders()[0]['items']),2)

    def test_stale_order_and_newly_introduced_overlap(self):
        order=self.initial();event=self.review([self.zips(),self.buttons()],['add','new']);preview=self.preview(event,order)
        with app.db() as c: c.execute('UPDATE order_lines SET quantity=12 WHERE order_id=?',(order,))
        self.assertEqual(self.request('/api/apply',self.payload(event,order,preview,'repeat',[None,None]))[0],400)
        self.assertEqual(len(app.orders()[0]['items']),1)
        fresh=self.preview(event,order);self.assertEqual(fresh['overlaps'][0]['existing'][0]['quantity'],12)
        with app.db() as c: c.execute('INSERT INTO order_lines VALUES (?,?,?,?,?)',('new-buttons',order,'buttons','white, packs',4))
        self.assertEqual(self.request('/api/apply',self.payload(event,order,fresh,'repeat',[None,None]))[0],400)
        fresh=self.preview(event,order);payload=self.payload(event,order,fresh,'repeat',[None,None]);self.assertEqual(self.request('/api/apply',payload)[0],400)
        payload['overlap_resolutions']['1']='repeat';self.assertEqual(self.request('/api/apply',payload)[0],200)
        self.assertEqual([i['quantity'] for i in app.orders()[0]['items']],[12,4])

    def test_wrong_order_targets_and_choice_cannot_bypass_checks(self):
        order=self.initial();event=self.review([self.zips()],['new']);preview=self.preview(event,order)
        for choice,target in [('',None),('new',None),('add','missing'),('replace',None)]:
            self.assertEqual(self.request('/api/apply',self.payload(event,order,preview,choice,[target]))[0],400)
        self.assertEqual(len(app.orders()[0]['items']),1)
        self.assertEqual(self.request('/api/apply-preview',{'event_id':event,'order_id':'missing'})[0],400)

if __name__=='__main__':unittest.main()
