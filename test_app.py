import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('orderthread', Path(__file__).parent / 'OrderThread/app.py')
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)

class AppTests(unittest.TestCase):
    def setUp(self):
        app.IMAGE_DRAFTS.clear()
        app.AUDIO_DRAFTS.clear()
        app.CATALOGUE_DRAFTS.clear()
        self.provider_environment=patch.dict(app.os.environ,{'AI_PROVIDER':'baseten','META_MODEL':'muse-spark-1.3'})
        self.provider_environment.start()
        self.temp = tempfile.TemporaryDirectory()
        self.original_db = app.DB
        app.DB = Path(self.temp.name) / 'test.db'
        self.server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        app.DB = self.original_db
        self.temp.cleanup()
        self.provider_environment.stop()

    def request(self, path, data=None):
        body = None if data is None else json.dumps(data, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(self.base + path, data=body, headers={'Content-Type':'application/json'})
        try:
            response = urllib.request.urlopen(req)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, response.headers, response.read().decode('utf-8')

    def payload(self):
        return {'message':'Ṣe 2 aṣọ àti 3 zips — café', 'proposal':{'items':[
            {'name':'aṣọ','quantity':2,'variant':'àwọ̀ buluu','evidence':'2 aṣọ'},
            {'name':'zips','quantity':3,'evidence':'3 zips'}]}, 'decisions':['new','repeat']}

    def test_mixed_decisions_and_legacy_history(self):
        legacy = {'message':'Old order','items':[{'name':'zip','quantity':1}], 'decision':'add'}
        with app.db() as connection:
            connection.execute('INSERT INTO events(kind,data) VALUES (?,?)', ('confirmed_proposal', json.dumps(legacy)))
        self.assertEqual(self.request('/api/confirm', self.payload())[0], 200)
        rows = json.loads(self.request('/api/events')[2])
        self.assertEqual(rows[0]['data'], legacy)
        self.assertEqual([i['decision'] for i in rows[1]['data']['items']], ['new','repeat'])
        self.assertEqual(rows[1]['data']['message'], self.payload()['message'])

    def test_validation_does_not_write(self):
        for mutation in ('missing','invalid','evidence','quantity'):
            payload = self.payload()
            if mutation == 'missing': payload['decisions'].pop()
            if mutation == 'invalid': payload['decisions'][0] = 'ignore'
            if mutation == 'evidence': payload['proposal']['items'][0]['evidence'] = 'invented'
            if mutation == 'quantity': payload['proposal']['items'][0]['quantity'] = True
            self.assertEqual(self.request('/api/confirm', payload)[0], 400)
        self.assertEqual(app.events(), [])

    def test_utf8_page_and_safe_errors(self):
        status, headers, html = self.request('/')
        self.assertEqual(status, 200)
        self.assertIn('charset=utf-8', headers['Content-Type'])
        self.assertIn('Review each item', html)
        self.assertIn('×', html)
        with patch.object(app, 'propose', side_effect=RuntimeError('secret-must-not-leak')):
            status, _, body = self.request('/api/propose', {'message':'test'})
        self.assertEqual(status, 500)
        self.assertNotIn('secret-must-not-leak', body)

    def save_review(self, items, decisions, submission=None):
        payload = {'message': '10 blue zips; 5 red zips; 7 green zips',
                   'proposal': {'items': items}, 'decisions': decisions}
        if submission: payload['submission_id'] = submission
        status, _, body = self.request('/api/confirm', payload)
        self.assertEqual(status, 200, body)
        return json.loads(body)['event_id']

    def zip_item(self, color='blue', quantity=10):
        return {'name':'zips', 'variant':color, 'quantity':quantity,
                'evidence':{'blue':'10 blue zips','red':'5 red zips','green':'7 green zips'}[color]}

    def initial_order(self):
        event = self.save_review([self.zip_item()], ['new'])
        payload = {'event_id':event, 'order_id':'__new__', 'order_name':'Test order',
                   'targets':[None], 'confirmed':True}
        status, _, body = self.request('/api/apply', payload)
        self.assertEqual(status, 200, body)
        return json.loads(body)['order_id']

    def test_repeat_and_red_addition_and_repeated_application(self):
        order = self.initial_order()
        event = self.save_review([self.zip_item(), self.zip_item('red',5)], ['repeat','add'])
        payload = {'event_id':event,'order_id':order,'targets':[None,'__new__'],'confirmed':True}
        comparison=json.loads(self.request('/api/apply-preview',{'event_id':event,'order_id':order})[2])
        payload.update(order_state=comparison['state_token'],overlap_resolutions={'0':'repeat'})
        for _ in range(2): self.assertEqual(self.request('/api/apply',payload)[0],200)
        lines = app.orders()[0]['items']
        self.assertEqual([(i['variant'],i['quantity']) for i in lines], [('blue',10),('red',5)])
        payload['targets']=[None,lines[0]['id']]
        self.assertEqual(self.request('/api/apply',payload)[0],400)
        self.assertEqual(len(app.orders()[0]['items']),2)

    def test_explicit_add_and_replace(self):
        order = self.initial_order()
        line = app.orders()[0]['items'][0]['id']
        event = self.save_review([self.zip_item()], ['add'])
        payload = {'event_id':event,'order_id':order,'targets':[line],'confirmed':True}
        comparison=json.loads(self.request('/api/apply-preview',{'event_id':event,'order_id':order})[2])
        payload.update(order_state=comparison['state_token'],overlap_resolutions={'0':'add'})
        self.assertEqual(self.request('/api/apply',payload)[0],200)
        self.assertEqual(app.orders()[0]['items'][0]['quantity'],20)
        event = self.save_review([self.zip_item('green',7)], ['replace'])
        payload['event_id']=event
        comparison=json.loads(self.request('/api/apply-preview',{'event_id':event,'order_id':order})[2])
        payload.update(order_state=comparison['state_token'],overlap_resolutions={})
        self.assertEqual(self.request('/api/apply',payload)[0],200)
        result = app.orders()[0]['items'][0]
        self.assertEqual((result['id'],result['variant'],result['quantity']),(line,'green',7))

    def test_missing_targets_confirmation_and_cross_order(self):
        order = self.initial_order()
        other = self.initial_order()
        wrong_line = app.orders()[1]['items'][0]['id']
        before = app.orders()
        for decision in ('add','replace'):
            event = self.save_review([self.zip_item('red',5)], [decision])
            for target, lines, confirmed in [(None,[None],True),(order,[None],True),
                    (order,[wrong_line],True),(order,['__new__'],False),('__new__',['__new__'],True)]:
                payload = {'event_id':event,'order_id':target,'targets':lines,
                           'confirmed':confirmed,'order_name':'Invalid'}
                self.assertEqual(self.request('/api/apply',payload)[0],400)
        self.assertEqual(app.orders(),before)

    def test_atomic_rollback_and_historical_records(self):
        order = self.initial_order()
        event = self.save_review([self.zip_item('red',5),self.zip_item('green',7)], ['add','replace'])
        before = app.orders()
        self.assertEqual(self.request('/api/apply',{'event_id':event,'order_id':order,
            'targets':['__new__','missing'],'confirmed':True})[0],400)
        self.assertEqual(app.orders(),before)
        with app.db() as c:
            cursor=c.execute('INSERT INTO events(kind,data) VALUES (?,?)',
                ('confirmed_proposal',json.dumps({'items':[self.zip_item()],'decision':'new'})))
            old=cursor.lastrowid
        self.assertEqual(self.request('/api/apply',{'event_id':old,'order_id':order,
            'targets':[None],'confirmed':True})[0],400)
        self.assertEqual(app.orders(),before)

    def test_repeated_review_submission(self):
        first=self.save_review([self.zip_item()],['new'],'same-review')
        second=self.save_review([self.zip_item()],['new'],'same-review')
        self.assertEqual(first,second)
        self.assertEqual(len(app.events()),1)
        self.assertEqual(app.orders(),[])

    def tracking_payload(self, kind='dispatch', quantity=4, submission='action-1'):
        order=self.initial_order()
        line=app.orders()[-1]['items'][0]['id']
        return {'order_id':order,'kind':kind,'items':[{'line_id':line,'quantity':quantity}],
                'submission_id':submission,'confirmed':True}

    def test_partial_full_dispatch_and_partial_receipt(self):
        payload=self.tracking_payload()
        self.assertEqual(self.request('/api/fulfillment',payload)[0],200)
        line=app.orders()[0]['items'][0]
        self.assertEqual((line['ordered'],line['dispatched'],line['outstanding_dispatch'],line['received']),(10,4,6,0))
        payload['submission_id']='receipt';payload['kind']='receipt';payload['items'][0]['quantity']=2
        self.assertEqual(self.request('/api/fulfillment',payload)[0],200)
        payload['submission_id']='remaining';payload['kind']='dispatch';payload['items'][0]['quantity']=6
        self.assertEqual(self.request('/api/fulfillment',payload)[0],200)
        result=app.orders()[0]
        line=result['items'][0]
        self.assertEqual((line['ordered'],line['dispatched'],line['outstanding_dispatch'],line['received']),(10,10,0,2))
        self.assertEqual([a['kind'] for a in result['fulfillment_history']],['dispatch','receipt','dispatch'])
        self.assertTrue(all(a['created'].endswith('Z') for a in result['fulfillment_history']))

    def test_invalid_tracking_quantities_and_targets(self):
        payload=self.tracking_payload()
        baseline=app.orders()
        for quantity in [-1,0,1.5,True,'4',None,11]:
            payload['items'][0]['quantity']=quantity
            self.assertEqual(self.request('/api/fulfillment',payload)[0],400)
        payload['items'][0]['quantity']=1;payload['kind']='receipt'
        self.assertEqual(self.request('/api/fulfillment',payload)[0],400)
        payload['kind']='dispatch';payload['confirmed']=False
        self.assertEqual(self.request('/api/fulfillment',payload)[0],400)
        payload['confirmed']=True;payload['items'].append(dict(payload['items'][0]))
        self.assertEqual(self.request('/api/fulfillment',payload)[0],400)
        payload['items']=[{'line_id':'missing','quantity':1}]
        self.assertEqual(self.request('/api/fulfillment',payload)[0],400)
        self.assertEqual(app.orders(),baseline)

    def test_tracking_retries_and_remaining_limits(self):
        payload=self.tracking_payload()
        for _ in range(2):self.assertEqual(self.request('/api/fulfillment',payload)[0],200)
        self.assertEqual(app.orders()[0]['items'][0]['dispatched'],4)
        self.assertEqual(len(app.orders()[0]['fulfillment_history']),1)
        payload['items'][0]['quantity']=3
        self.assertEqual(self.request('/api/fulfillment',payload)[0],400)
        payload['submission_id']='over-remaining';payload['items'][0]['quantity']=7
        self.assertEqual(self.request('/api/fulfillment',payload)[0],400)
        payload['submission_id']='receipt';payload['kind']='receipt';payload['items'][0]['quantity']=3
        for _ in range(2):self.assertEqual(self.request('/api/fulfillment',payload)[0],200)
        payload['submission_id']='too-much-receipt';payload['items'][0]['quantity']=2
        self.assertEqual(self.request('/api/fulfillment',payload)[0],400)
        self.assertEqual(app.orders()[0]['items'][0]['received'],3)

    def test_tracking_persists_after_server_restart(self):
        payload=self.tracking_payload()
        self.assertEqual(self.request('/api/fulfillment',payload)[0],200)
        before=app.orders()
        self.server.shutdown();self.server.server_close();self.thread.join()
        self.server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base='http://127.0.0.1:'+str(self.server.server_port)
        self.assertEqual(json.loads(self.request('/api/orders')[2]),before)
        response=json.loads(self.request('/api/fulfillment',payload)[2])
        self.assertTrue(response['already_recorded'])
        self.assertEqual(app.orders(),before)

    def test_tracking_batch_rollback_and_replacement_guard(self):
        payload=self.tracking_payload()
        payload['items'].append({'line_id':'missing','quantity':1})
        self.assertEqual(self.request('/api/fulfillment',payload)[0],400)
        self.assertEqual(app.orders()[0]['fulfillment_history'],[])
        payload['items'].pop()
        self.assertEqual(self.request('/api/fulfillment',payload)[0],200)
        event=self.save_review([self.zip_item('green',7)],['replace'])
        self.assertEqual(self.request('/api/apply',{'event_id':event,'order_id':payload['order_id'],
            'targets':[payload['items'][0]['line_id']],'confirmed':True})[0],400)
        self.assertEqual(app.orders()[0]['items'][0]['variant'],'blue')

    def image_fixture(self, fmt='PNG'):
        import io,base64
        from PIL import Image
        buffer=io.BytesIO();Image.new('RGB',(20,20),'white').save(buffer,format=fmt)
        return {'mime':'image/png' if fmt=='PNG' else 'image/jpeg',
                'base64':base64.b64encode(buffer.getvalue()).decode('ascii')}

    def image_response(self, items=None):
        import io
        proposal={'items':items if items is not None else [
            {'name':'zips','quantity':10,'variant':'blue','uncertain':False,'evidence':'invented quote'},
            {'name':'buttons','quantity':None,'variant':None,'uncertain':True,'uncertainty':'Quantity unreadable'}],
            'intent':'unclear','clarification':'Check the second row','fulfillment_note':''}
        return io.BytesIO(json.dumps({'choices':[{'message':{'content':json.dumps(proposal)}}]}).encode())

    def extract_image(self):
        with patch.dict(app.os.environ,{'BASETEN_API_KEY':'test-placeholder'}), patch.object(
                app.urllib.request,'urlopen',return_value=self.image_response()):
            return app.propose_image(self.image_fixture())

    def test_image_provider_contract_and_uncertainty(self):
        import base64
        for fmt in ('PNG','JPEG'):
            with patch.dict(app.os.environ,{'BASETEN_API_KEY':'test-placeholder'}), patch.object(
                    app.urllib.request,'urlopen',return_value=self.image_response()) as provider:
                image=self.image_fixture(fmt);proposal=app.propose_image(image)
            payload=json.loads(provider.call_args.args[0].data)
            self.assertEqual(payload['model'],app.MODEL)
            parts=payload['messages'][1]['content']
            self.assertEqual(parts[1]['type'],'image_url')
            self.assertEqual(parts[1]['image_url']['url'],'data:'+image['mime']+';base64,'+image['base64'])
            self.assertIsNone(proposal['items'][0]['evidence'])
            self.assertFalse(proposal['items'][0]['uncertain'])
            self.assertTrue(proposal['items'][1]['uncertain'])
            self.assertIsNone(proposal['items'][1]['quantity'])
        self.assertEqual(app.events(),[])
        self.assertEqual(app.orders(),[])
        with app.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM source_images').fetchone()[0],0)

    def test_image_confirmation_citation_and_human_correction(self):
        import base64
        proposal=self.extract_image()
        payload={'message':'','proposal':proposal,'decisions':['new','new'],
                 'image_draft_id':proposal['image_draft_id'],'submission_id':'image-review'}
        self.assertEqual(self.request('/api/confirm',payload)[0],400)
        payload['image_reviewed']=True
        self.assertEqual(self.request('/api/confirm',payload)[0],400)
        proposal['items'][1]['quantity']=5
        status,_,body=self.request('/api/confirm',payload);self.assertEqual(status,200,body)
        event_id=json.loads(body)['event_id']
        self.assertEqual(self.request('/api/confirm',payload)[0],200)
        record=app.events()[0]['data']
        self.assertEqual(len(app.events()),1)
        self.assertEqual(record['source_type'],'image')
        self.assertTrue(record['items'][1]['human_verified'])
        self.assertEqual(record['items'][1]['quantity'],5)
        self.assertIsNone(record['items'][0]['evidence'])
        self.assertIsNone(record['extracted_proposal']['items'][1]['quantity'])
        self.assertEqual(app.orders(),[])
        with urllib.request.urlopen(self.base+'/api/images/'+record['source_id']) as image:
            self.assertEqual(image.headers['Content-Type'],'image/png')
            self.assertEqual(image.read(),base64.b64decode(self.image_fixture()['base64']))
        status,_,_=self.request('/api/apply',{'event_id':event_id,'order_id':'__new__',
            'order_name':'Image order','targets':[None,None],'confirmed':True})
        self.assertEqual(status,200)
        self.assertEqual([i['quantity'] for i in app.orders()[0]['items']],[10,5])

    def test_invalid_images_never_reach_provider(self):
        import base64
        image=self.image_fixture()
        cases=[None,{'mime':'image/svg+xml','base64':image['base64']},
            {'mime':'image/jpeg','base64':image['base64']},
            {'mime':'image/png','base64':'!!!'},
            {'mime':'image/png','base64':base64.b64encode(b'not an image').decode()},
            {'mime':'image/png','base64':''},
            {'mime':'image/png','base64':'A'*(4*((app.MAX_IMAGE_BYTES+2)//3)+4)}]
        with patch.object(app.urllib.request,'urlopen') as provider:
            for value in cases:
                with self.assertRaises(ValueError):app.propose_image(value)
            with patch.object(app,'MAX_IMAGE_PIXELS',10):
                with self.assertRaises(ValueError):app.propose_image(image)
            provider.assert_not_called()
        self.assertEqual(app.events(),[])

    def test_image_expiry_forgery_and_invalid_model_response(self):
        proposal=self.extract_image()
        payload={'message':'','proposal':proposal,'decisions':['new','new'],
                 'image_draft_id':'missing','image_reviewed':True}
        self.assertEqual(self.request('/api/confirm',payload)[0],400)
        payload.pop('image_draft_id')
        self.assertEqual(self.request('/api/confirm',payload)[0],400)
        with patch.object(app,'IMAGE_DRAFT_TTL',-1):
            with self.assertRaises(ValueError):app.image_draft(proposal['image_draft_id'])
        with patch.dict(app.os.environ,{'BASETEN_API_KEY':'test-placeholder'}), patch.object(
                app.urllib.request,'urlopen',return_value=self.image_response(items=['invalid'])):
            with self.assertRaises(ValueError):app.propose_image(self.image_fixture())
        self.assertEqual(app.events(),[])

    def test_provider_text_routing_and_parameters(self):
        import io
        for provider, endpoint, model in [
            ('baseten','https://inference.baseten.co/v1/chat/completions',app.MODEL),
            ('meta','https://api.meta.ai/v1/chat/completions','muse-spark-1.3')]:
            proposal=self.payload()['proposal'] | {'intent':'new'}
            response=io.BytesIO(json.dumps({'choices':[{'message':{'content':json.dumps(proposal)}}]}).encode())
            with patch.dict(app.os.environ,{'BASETEN_API_KEY':'baseten-test-placeholder','MODEL_API_KEY':'meta-test-placeholder'}), patch.object(app.urllib.request,'urlopen',return_value=response) as transport:
                result=app.propose(self.payload()['message'],provider)
            request=transport.call_args.args[0]
            self.assertEqual(request.full_url,endpoint)
            payload=json.loads(request.data)
            self.assertEqual(payload['model'],model)
            self.assertEqual(result['ai'],{'provider':provider,'model':model})
            if provider=='meta':
                self.assertEqual(payload['messages'][0]['role'],'developer')
                self.assertNotIn('temperature',payload)
                self.assertNotIn('modalities',payload)
            else:
                self.assertEqual(payload['temperature'],0)
                self.assertEqual(payload['messages'][0]['role'],'system')
            expected='Bearer '+('meta-test-placeholder' if provider=='meta' else 'baseten-test-placeholder')
            self.assertTrue(request.get_header('Authorization')==expected)

    def test_meta_image_routing_preserves_citation_contract(self):
        with patch.dict(app.os.environ,{'MODEL_API_KEY':'meta-test-placeholder'}), patch.object(
                app.urllib.request,'urlopen',return_value=self.image_response()) as transport:
            proposal=app.propose_image(self.image_fixture(),'meta')
        request=transport.call_args.args[0];payload=json.loads(request.data)
        self.assertEqual(request.full_url,'https://api.meta.ai/v1/chat/completions')
        self.assertEqual(payload['model'],'muse-spark-1.3')
        self.assertTrue(payload['messages'][1]['content'][1]['image_url']['url'].startswith('data:image/png;base64,'))
        self.assertEqual(proposal['ai']['provider'],'meta')
        self.assertIsNone(proposal['items'][0]['evidence'])
        self.assertTrue(proposal['items'][1]['uncertain'])
        self.assertEqual(app.events(),[])

    def test_provider_status_and_missing_credential_no_fallback(self):
        with patch.dict(app.os.environ,{'AI_PROVIDER':'meta','MODEL_API_KEY':'','BASETEN_API_KEY':'private-test-sentinel'}):
            status=json.loads(self.request('/api/status')[2])
            self.assertEqual(status['default_provider'],'meta')
            self.assertFalse(status['configured'])
            meta=next(p for p in status['providers'] if p['id']=='meta')
            self.assertEqual(meta['model'],'muse-spark-1.3')
            self.assertEqual(meta['input_modalities'],['text','image'])
            self.assertNotIn('private-test-sentinel',json.dumps(status))
            with patch.object(app.urllib.request,'urlopen') as transport:
                with self.assertRaisesRegex(ValueError,'MODEL_API_KEY'):app.propose('hello')
                transport.assert_not_called()
        with patch.dict(app.os.environ,{'AI_PROVIDER':'not-valid'}):
            self.assertFalse(app.provider_status()['configured'])
            with self.assertRaises(ValueError):app.provider_config()

    def test_provider_model_validation_and_server_selection(self):
        for model in ('meta-models/muse-spark-open-1026','muse-image-1.0','muse-voice-transcribe-1.0'):
            with patch.dict(app.os.environ,{'META_MODEL':model}):
                with self.assertRaises(ValueError):app.provider_config('meta')
                status=app.provider_status()
                self.assertFalse(next(p for p in status['providers'] if p['id']=='meta')['configured'])
        with patch.dict(app.os.environ,{'META_MODEL':'muse-spark-1.2'}):
            self.assertEqual(app.provider_config('meta')['model'],'muse-spark-1.2')
        with patch.object(app,'propose',return_value={'items':[]}) as extraction:
            self.assertEqual(self.request('/api/propose',{'message':'hello','provider':'meta'})[0],200)
            extraction.assert_called_once_with('hello','meta')
        with patch.object(app,'propose_image',return_value={'items':[]}) as extraction:
            image=self.image_fixture()
            self.assertEqual(self.request('/api/propose-image',{'image':image,'provider':'meta'})[0],200)
            extraction.assert_called_once_with(image,'meta')

    def test_provider_errors_do_not_disclose_response_or_credentials(self):
        import io
        error=urllib.error.HTTPError('https://api.meta.ai/v1/chat/completions',401,'private-test-sentinel',{},io.BytesIO(b'private-test-sentinel'))
        with patch.dict(app.os.environ,{'MODEL_API_KEY':'private-test-sentinel'}), patch.object(app.urllib.request,'urlopen',side_effect=error):
            with self.assertRaises(app.ProviderError) as raised:app.propose('hello','meta')
            self.assertNotIn('private-test-sentinel',str(raised.exception))
            self.assertIn('HTTP 401',str(raised.exception))
        with patch.object(app,'propose',side_effect=app.ProviderError('Meta Model API returned HTTP 429.')):
            status,_,body=self.request('/api/propose',{'message':'hello','provider':'meta'})
            self.assertEqual(status,502)
            self.assertIn('Meta Model API',body)

    def test_mock_extraction(self):
        proposal = self.payload()['proposal'] | {'intent':'new'}
        response = json.dumps({'choices':[{'message':{'content':json.dumps(proposal)}}]}).encode()
        import io
        with patch.dict(app.os.environ, {'BASETEN_API_KEY':'test-placeholder'}), patch.object(app.urllib.request, 'urlopen', return_value=io.BytesIO(response)):
            result = app.propose(self.payload()['message'])
        self.assertEqual(len(result['items']), 2)

if __name__ == '__main__':
    unittest.main()
