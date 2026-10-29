import base64,io,json,wave
from unittest.mock import patch
from test_app import AppTests,app

def wav_audio(rate=16000,seconds=1):
    buffer=io.BytesIO()
    with wave.open(buffer,'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(b'\0\0'*int(rate*seconds))
    return {'mime':'audio/wav','base64':base64.b64encode(buffer.getvalue()).decode()}

def provider_result(items=None,transcript="I've sent the list; I'll pick it up tomorrow",clarification=''):
    return {'choices':[{'message':{'content':json.dumps({'transcript':transcript,'items':items or [],'intent':'unclear','fulfillment_note':'Pick up tomorrow','clarification':clarification})}}]}

class AudioTests(AppTests):
    def extract(self,result=None):
        with patch.object(app,'ai_completion',return_value=(result or provider_result(),{'provider':'baseten','model':app.MODEL})):
            status,_,body=self.request('/api/propose-audio',{'provider':'baseten','audio':wav_audio()})
        self.assertEqual(status,200,body)
        return json.loads(body)
    def save(self,p,**changes):
        data={'proposal':p,'audio_draft_id':p['audio_draft_id'],'audio_reviewed':True,'decisions':['new']*len(p['items']),'submission_id':'audio-test'}
        data.update(changes)
        return self.request('/api/confirm',data)
    def test_audio_instructions_confirmation_retry_and_no_order(self):
        p=self.extract();self.assertEqual(p['items'],[]);self.assertEqual(app.events(),[])
        self.assertEqual(self.save(p,audio_reviewed=False)[0],400)
        self.assertEqual(app.events(),[])
        p['transcript']='I sent the list. I will collect tomorrow.';p['fulfillment_note']='Customer will collect tomorrow.'
        first=self.save(p);self.assertEqual(first[0],200);self.assertEqual(self.save(p)[2],first[2]);self.assertEqual(len(app.events()),1)
        record=app.events()[0]['data'];self.assertEqual(record['source_type'],'audio');self.assertEqual(record['transcript'],p['transcript']);self.assertNotEqual(record['extracted_proposal']['transcript'],p['transcript'])
        self.assertEqual(self.request('/api/apply',{'event_id':json.loads(first[2])['event_id'],'order_id':'__new__','order_name':'Forbidden','targets':[],'confirmed':True})[0],400)
        self.assertEqual(json.loads(self.request('/api/orders')[2]),[])
    def test_audio_uncertainty_correction_expiry_and_forgery(self):
        p=self.extract(provider_result([{'name':'zips','quantity':None,'uncertain':True}],transcript='[unclear] zips'))
        self.assertTrue(p['clarification']);self.assertEqual(self.save(p)[0],400)
        p['items'][0]['quantity']=3
        self.assertEqual(self.save(p)[0],400)
        self.assertEqual(self.save(p,clarification_resolved=True)[0],200)
        self.assertEqual(self.save(p,audio_draft_id='forged')[0],400)
        with patch.object(app.time,'monotonic',return_value=app.time.monotonic()+1801): self.assertEqual(self.save(p)[0],400)
    def test_audio_items_require_separate_apply_confirmation(self):
        p=self.extract(provider_result([{'name':'zips','quantity':2,'variant':'blue','uncertain':False}]))
        saved=json.loads(self.save(p)[2])
        self.assertEqual(json.loads(self.request('/api/orders')[2]),[])
        payload={'event_id':saved['event_id'],'order_id':'__new__','order_name':'Synthetic audio order','targets':[None]}
        self.assertEqual(self.request('/api/apply',payload)[0],400)
        payload['confirmed']=True
        self.assertEqual(self.request('/api/apply',payload)[0],200)
        order=json.loads(self.request('/api/orders')[2])[0]
        self.assertEqual(order['items'][0]['quantity'],2)
        self.assertEqual(order['items'][0]['dispatched'],0)
        self.assertEqual(order['items'][0]['received'],0)

    def test_audio_validation_and_provider_request(self):
        for audio in ({'mime':'audio/mp3','base64':'AAAA'}, {'mime':'audio/wav','base64':'!'}, {'mime':'audio/wav','base64':base64.b64encode(b'not wav').decode()},wav_audio(4000),wav_audio(seconds=61),{'mime':'audio/wav','base64':'A'*(4*((app.MAX_AUDIO_BYTES+2)//3)+1)}):
            with patch.object(app,'ai_completion') as provider:
                self.assertEqual(self.request('/api/propose-audio',{'audio':audio})[0],400);provider.assert_not_called()
        with patch.dict(app.os.environ,{'BASETEN_API_KEY':'test-only'}),patch.object(app.urllib.request,'urlopen',return_value=io.BytesIO(json.dumps(provider_result()).encode())) as provider:
            app.propose_audio(wav_audio(),'baseten')
            payload=json.loads(provider.call_args.args[0].data)
            self.assertEqual(payload['model'],app.MODEL);self.assertEqual(payload['messages'][1]['content'][1]['type'],'audio_url');self.assertTrue(payload['messages'][1]['content'][1]['audio_url']['url'].startswith('data:audio/wav;base64,'))
        with patch.object(app,'ai_completion',return_value=({'choices':[]},{})):
            self.assertEqual(self.request('/api/propose-audio',{'audio':wav_audio()})[0],400)
        self.assertEqual(self.request('/api/propose-audio',{'audio':wav_audio(),'provider':'meta'})[0],400)

if __name__=='__main__':
    import unittest
    unittest.main()
