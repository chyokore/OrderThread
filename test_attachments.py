import base64,io,json,threading,unittest,urllib.request
from unittest.mock import patch
from PIL import Image
from test_audio import app,AppTests,wav_audio,provider_result

class AttachmentTests(unittest.TestCase):
    setUp=AppTests.setUp
    tearDown=AppTests.tearDown
    request=AppTests.request

    def image_review(self):
        image=io.BytesIO();Image.new('RGB',(30,30),'white').save(image,format='PNG')
        extraction={'items':[{'name':'zips','quantity':10,'variant':'blue','uncertain':False},{'name':'zips','quantity':5,'variant':'red','uncertain':False}],'intent':'new','clarification':'','fulfillment_note':''}
        with patch.object(app,'ai_completion',return_value=({'choices':[{'message':{'content':json.dumps(extraction)}}]}, {'provider':'baseten','model':app.MODEL})):
            status,_,body=self.request('/api/propose-image',{'image':{'mime':'image/png','base64':base64.b64encode(image.getvalue()).decode()},'provider':'baseten'})
        self.assertEqual(status,200,body);proposal=json.loads(body)
        status,_,body=self.request('/api/confirm',{'proposal':proposal,'decisions':['new','new'],'image_draft_id':proposal['image_draft_id'],'image_reviewed':True})
        self.assertEqual(status,200,body);return json.loads(body)['event_id']

    def voice_review(self):
        response=provider_result(transcript='The buyer will pick it up tomorrow.')
        with patch.object(app,'ai_completion',return_value=(response,{'provider':'baseten','model':app.MODEL})):
            status,_,body=self.request('/api/propose-audio',{'audio':wav_audio(),'provider':'baseten'})
        self.assertEqual(status,200,body);proposal=json.loads(body);proposal['fulfillment_note']='Buyer will pick it up tomorrow.'
        status,_,body=self.request('/api/confirm',{'proposal':proposal,'decisions':[],'audio_draft_id':proposal['audio_draft_id'],'audio_reviewed':True,'submission_id':'voice-save'})
        self.assertEqual(status,200,body);return json.loads(body)['event_id']

    def order_from(self,event,name='Image order'):
        status,_,body=self.request('/api/apply',{'event_id':event,'order_id':'__new__','order_name':name,'targets':[None,None],'confirmed':True})
        self.assertEqual(status,200,body);return json.loads(body)['order_id']

    def attach(self,event,order,submission='attachment-1',**changes):
        payload={'event_id':event,'order_id':order,'submission_id':submission,'confirmed':True};payload.update(changes)
        return self.request('/api/attach-review',payload)

    def get_orders(self): return json.loads(self.request('/api/orders')[2])

    def test_image_order_plus_instruction_only_voice_and_separate_sources(self):
        image=self.image_review();order=self.order_from(image);voice=self.voice_review()
        originals={e['id']:e for e in app.events() if e['kind']=='confirmed_proposal'}
        before=self.get_orders()[0]
        self.assertEqual(self.attach(voice,order,confirmed=False)[0],400)
        self.assertEqual(self.get_orders()[0]['reviews'],before['reviews'])
        self.assertEqual(self.attach(voice,order)[0],200)
        after=self.get_orders()[0];self.assertEqual(after['items'],before['items']);self.assertEqual(after['fulfillment_history'],[])
        self.assertEqual([(i['variant'],i['ordered']) for i in after['items']],[('blue',10),('red',5)])
        self.assertEqual([(r['relation'],r['review']['source_type']) for r in after['reviews']],[('applied','image'),('attached','audio')])
        note=after['reviews'][1]['review'];self.assertEqual(note['items'],[]);self.assertIn('tomorrow',note['fulfillment_note']);self.assertTrue(note['transcript_label'].startswith('AI-generated'))
        self.assertEqual(self.attach(image,order,'attach-image')[0],200)
        self.assertEqual(self.get_orders()[0]['items'],before['items'])
        self.assertEqual(originals,{e['id']:e for e in app.events() if e['kind']=='confirmed_proposal'})
        source=after['reviews'][0]['review']['source_id']
        with urllib.request.urlopen(self.base+'/api/images/'+source) as response:
            self.assertEqual(response.status,200);self.assertEqual(response.headers['Content-Type'],'image/png')

    def test_missing_invalid_wrong_targets_and_reviews(self):
        image=self.image_review();order=self.order_from(image);voice=self.voice_review()
        for target in ('',None,'__new__','nonexistent'):
            self.assertEqual(self.attach(voice,target)[0],400)
        for event in (None,True,9999): self.assertEqual(self.attach(event,order)[0],400)
        self.assertEqual(self.attach(voice,order,submission='')[0],400)
        other=self.order_from(self.image_review(),'Other order')
        self.assertEqual(self.attach(image,other)[0],400)
        self.assertEqual(self.attach(voice,order)[0],200)
        self.assertEqual(self.attach(voice,other,'different-target')[0],400)
        with app.db() as c:
            legacy=c.execute('INSERT INTO events(kind,data) VALUES (?,?)',('confirmed_proposal',json.dumps({'message':'legacy','items':[]}))).lastrowid
        self.assertEqual(self.attach(legacy,order,'legacy')[0],400)
        audit=next(e['id'] for e in app.events() if e['kind']=='order_applied')
        self.assertEqual(self.attach(audit,order,'audit')[0],400)

    def test_retry_and_duplicate_links_preserve_quantities_and_audit(self):
        order=self.order_from(self.image_review());voice=self.voice_review()
        first=json.loads(self.attach(voice,order)[2]);second=json.loads(self.attach(voice,order)[2]);third=json.loads(self.attach(voice,order,'new-request')[2])
        self.assertEqual(first['attachment_id'],second['attachment_id']);self.assertEqual(first['attachment_id'],third['attachment_id']);self.assertTrue(second['already_attached']);self.assertTrue(third['already_attached'])
        self.assertEqual(len([e for e in app.events() if e['kind']=='order_review_attached']),1)
        self.assertEqual(self.attach(self.image_review(),order)[0],400)
        self.assertEqual(len(self.get_orders()[0]['items']),2)

    def test_text_attachment_does_not_apply_and_blocks_wrong_order_apply(self):
        order=self.order_from(self.image_review());other=self.order_from(self.image_review(),'Other')
        status,_,body=self.request('/api/confirm',{'message':'2 green zips','proposal':{'items':[{'name':'zips','quantity':2,'variant':'green','evidence':'2 green zips'}]},'decisions':['new']})
        self.assertEqual(status,200);text=json.loads(body)['event_id'];before=self.get_orders()
        self.assertEqual(self.attach(text,order)[0],200)
        self.assertEqual([o['items'] for o in before],[o['items'] for o in self.get_orders()])
        self.assertEqual(self.request('/api/apply',{'event_id':text,'order_id':other,'targets':[None],'confirmed':True})[0],400)
        self.assertEqual(self.request('/api/apply',{'event_id':text,'order_id':order,'targets':[None],'confirmed':True})[0],200)
        self.assertEqual(self.get_orders()[0]['items'][-1]['quantity'],2)

    def test_concurrent_attachment_retries_create_one_link_and_audit(self):
        order=self.order_from(self.image_review());voice=self.voice_review();results=[]
        threads=[threading.Thread(target=lambda key=key: results.append(self.attach(voice,order,key)[0])) for key in ('parallel-a','parallel-b')]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertEqual(sorted(results),[200,200])
        self.assertEqual(len([r for r in self.get_orders()[0]['reviews'] if r['relation']=='attached']),1)
        self.assertEqual(len([e for e in app.events() if e['kind']=='order_review_attached']),1)

    def test_restart_preserves_attachment_dispatch_receipt_and_legacy_history(self):
        order=self.order_from(self.image_review());line=self.get_orders()[0]['items'][0]['id']
        for kind,quantity in [('dispatch',4),('receipt',2)]:
            self.assertEqual(self.request('/api/fulfillment',{'order_id':order,'kind':kind,'items':[{'line_id':line,'quantity':quantity}],'submission_id':kind,'confirmed':True})[0],200)
        before=self.get_orders()[0];voice=self.voice_review();self.assertEqual(self.attach(voice,order)[0],200)
        self.server.shutdown();self.server.server_close();self.thread.join()
        self.server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.base='http://127.0.0.1:'+str(self.server.server_port)
        after=self.get_orders()[0];self.assertEqual(after['items'],before['items']);self.assertEqual(after['fulfillment_history'],before['fulfillment_history']);self.assertEqual(after['reviews'][-1]['review_id'],voice)
        self.assertTrue(json.loads(self.attach(voice,order)[2])['already_attached'])
        self.assertEqual(len([e for e in app.events() if e['kind']=='order_review_attached']),1)

if __name__=='__main__': unittest.main()
