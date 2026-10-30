import base64, copy, io, json, subprocess, tempfile, unittest, urllib.request, urllib.error
from pathlib import Path
from unittest.mock import patch
from test_app import AppTests, app
import imageio_ffmpeg


def synthetic_video(duration=2, suffix='mp4', codec='libx264'):
    with tempfile.TemporaryDirectory() as folder:
        path=Path(folder)/('synthetic.'+suffix)
        command=[imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-f','lavfi','-i',f'color=c=blue:s=320x240:r=4:d={duration}','-an','-c:v',codec]
        if suffix in ('mp4','mov'):command+=['-pix_fmt','yuv420p']
        subprocess.run(command+[str(path)],capture_output=True,check=True,timeout=30)
        return path.read_bytes()


def upload(content, name='synthetic.mp4', mime='video/mp4'):
    return {'video':{'name':name,'mime':mime,'base64':base64.b64encode(content).decode()}}


def image_result(uncertain=False):
    return {'choices':[{'message':{'content':json.dumps({'items':[{'name':'zips','quantity':None if uncertain else 10,'variant':None if uncertain else 'Blue, 20 cm','uncertain':uncertain,'uncertainty':'Quantity and colour unclear' if uncertain else ''}],'intent':'unclear','clarification':'Ask buyer' if uncertain else '', 'fulfillment_note':''})}}]}


class VideoFrameTests(unittest.TestCase):
    setUp=AppTests.setUp
    tearDown=AppTests.tearDown
    request=AppTests.request

    @classmethod
    def setUpClass(cls):
        cls.mp4=synthetic_video()
        cls.webm=synthetic_video(suffix='webm',codec='libvpx-vp9')
        cls.mov=synthetic_video(suffix='mov')

    def start(self):
        app.VIDEO_DRAFTS.clear()
        status,_,body=self.request('/api/video-preview',upload(self.mp4))
        self.assertEqual(status,200,body)
        return json.loads(body)['video_draft_id']

    def frame(self,token,position=0):
        status,_,body=self.request('/api/video-frame',{'video_draft_id':token,'position':position})
        self.assertEqual(status,200,body)
        return json.loads(body)

    def proposal(self, token, frame, uncertain=False):
        with patch.object(app,'ai_completion',return_value=(image_result(uncertain),{'provider':'baseten','model':'mock-image-model'})) as ai:
            status,_,body=self.request('/api/propose-image',{'video_draft_id':token,'frame_id':frame['frame_id'],'provider':'baseten'})
            self.assertEqual(status,200,body)
            parts=ai.call_args.args[0][1]['content']
            self.assertEqual([p['type'] for p in parts],['text','image_url'])
            self.assertTrue(parts[1]['image_url']['url'].startswith('data:image/png;base64,'))
        return json.loads(body)

    def confirm(self,proposal):
        return {'proposal':proposal,'decisions':['new'],'image_draft_id':proposal['image_draft_id'],'image_reviewed':True,'submission_id':'frame-review'}

    def test_supported_real_containers_and_no_early_persistence(self):
        app.VIDEO_DRAFTS.clear()
        for content,suffix,mime in [(self.mp4,'mp4','video/mp4'),(self.webm,'webm','video/webm'),(self.mov,'mov','video/quicktime')]:
            status,_,body=self.request('/api/video-preview',upload(content,'synthetic.'+suffix,mime))
            self.assertEqual(status,200,body);self.assertAlmostEqual(json.loads(body)['duration'],2)
        with app.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM source_videos').fetchone()[0],0)
        self.assertEqual(json.loads(self.request('/api/events')[2]),[])

    def test_invalid_type_content_and_conversion_failure(self):
        app.VIDEO_DRAFTS.clear()
        for data in [upload(b'not a video'),upload(self.mp4,'renamed.webm','video/webm'),upload(self.mp4,'test.mp4','video/webm'),upload(self.mp4,'test.exe'),{'video':{'name':'x.mp4','mime':'video/mp4','base64':'!'}},upload(self.mp4[:40])]:
            self.assertEqual(self.request('/api/video-preview',data)[0],400)
        with patch.object(app.subprocess,'run',side_effect=subprocess.TimeoutExpired('ffmpeg',30)):
            self.assertIn('unreadable',self.request('/api/video-preview',upload(self.mp4))[2])
        with patch.object(app,'MAX_VIDEO_BYTES',100):self.assertEqual(self.request('/api/video-preview',upload(self.mp4))[0],400)

    def test_duration_limit_real_video(self):
        app.VIDEO_DRAFTS.clear()
        status,_,body=self.request('/api/video-preview',upload(synthetic_video(61)))
        self.assertEqual(status,400);self.assertIn('60 seconds',body)

    def test_explicit_selection_limit_removal_duplicate_and_bad_position(self):
        token=self.start();frame=self.frame(token)
        self.assertEqual(self.frame(token)['frame_id'],frame['frame_id'])
        self.frame(token,.5);self.frame(token,1)
        self.assertEqual(self.request('/api/video-frame',{'video_draft_id':token,'position':1.5})[0],400)
        self.assertEqual(self.request('/api/video-frame-remove',{'video_draft_id':token,'frame_id':frame['frame_id']})[0],200)
        self.frame(token,1.5)
        for position in [-1,2,float('nan'),True,'0']:
            self.assertEqual(self.request('/api/video-frame',{'video_draft_id':token,'position':position})[0],400)
        self.assertEqual(self.request('/api/propose-image',{'video_draft_id':token,'frame_id':'wrong'})[0],400)
        app.VIDEO_DRAFTS[token]['created']-=1801
        self.assertEqual(self.request('/api/video-frame',{'video_draft_id':token,'position':0})[0],400)

    def test_image_only_provider_human_confirmation_forgery_and_persistence(self):
        token=self.start();frame=self.frame(token,.5);proposal=self.proposal(token,frame);payload=self.confirm(proposal)
        bad=copy.deepcopy(payload);bad['image_reviewed']=False
        self.assertEqual(self.request('/api/confirm',bad)[0],400)
        self.assertEqual(json.loads(self.request('/api/events')[2]),[])
        proposal['video_source']['source_id']='forged'
        self.assertEqual(self.request('/api/confirm',payload)[0],200)
        self.assertEqual(self.request('/api/confirm',payload)[0],200)
        app.IMAGE_DRAFTS.clear();app.VIDEO_DRAFTS.clear()
        rows=json.loads(self.request('/api/events')[2]);self.assertEqual(len(rows),1)
        record=rows[0]['data'];meta=record['video_source']
        self.assertNotEqual(meta['source_id'],'forged');self.assertEqual(meta['selected_position'],.5)
        self.assertEqual(record['source_type'],'image');self.assertIsNone(record['items'][0]['evidence'])
        with app.db() as c:
            saved=c.execute('SELECT content FROM source_videos WHERE id=?',(meta['source_id'],)).fetchone()[0]
            self.assertEqual(saved,self.mp4)
        req=urllib.request.Request(self.base+'/api/videos/'+meta['source_id'],headers={'Range':'bytes=0-15'})
        with urllib.request.urlopen(req) as r:self.assertEqual(r.status,206);self.assertEqual(r.read(),self.mp4[:16])
        with urllib.request.urlopen(self.base+'/api/images/'+record['source_id']) as r:self.assertTrue(r.read().startswith(bytes.fromhex('89504e47')))
        self.assertEqual(json.loads(self.request('/api/orders')[2]),[])

    def test_uncertainty_requires_clarification_and_no_invented_quantity(self):
        token=self.start();proposal=self.proposal(token,self.frame(token),True)
        self.assertIsNone(proposal['items'][0]['quantity']);self.assertIsNone(proposal['items'][0]['variant'])
        payload=self.confirm(proposal);self.assertEqual(self.request('/api/confirm',payload)[0],400)
        proposal['items'][0].update(quantity=10,variant='Blue, confirmed by buyer')
        self.assertEqual(self.request('/api/confirm',payload)[0],400)
        payload['clarification_resolved']=True
        self.assertEqual(self.request('/api/confirm',payload)[0],200)

    def test_separate_audio_review_links_to_same_order_without_item_changes(self):
        from test_audio import provider_result, wav_audio
        token=self.start();p=self.proposal(token,self.frame(token));payload=self.confirm(p)
        event=json.loads(self.request('/api/confirm',payload)[2])['event_id']
        applied=json.loads(self.request('/api/apply',{'event_id':event,'order_id':'__new__','order_name':'Synthetic video order','targets':[None],'confirmed':True})[2])
        orders=json.loads(self.request('/api/orders')[2]);self.assertEqual(len(orders),1)
        oid=orders[0]['id'];before=orders[0]['items']
        with patch.object(app,'ai_completion',return_value=(provider_result(),{'provider':'baseten','model':'mock-audio-model'})):
            result=app.propose_audio(wav_audio(),'baseten')
        self.assertNotIn('video_source',result);self.assertEqual(result['items'],[])
        audio=app.confirm_audio({'audio_draft_id':result['audio_draft_id'],'audio_reviewed':True,'proposal':result,'decisions':[],'submission_id':'separate-speech','clarification_resolved':True})
        self.assertEqual(self.request('/api/attach-review',{'event_id':audio['event_id'],'order_id':oid,'confirmed':True,'submission_id':'attach-speech'})[0],200)
        app.VIDEO_DRAFTS.clear();app.IMAGE_DRAFTS.clear();app.AUDIO_DRAFTS.clear()
        order=json.loads(self.request('/api/orders')[2])[0]
        self.assertEqual(order['items'],before);self.assertEqual(len(order['reviews']),2)
        self.assertTrue(any(r['review'].get('video_source') for r in order['reviews']))
        self.assertTrue(any(r['review'].get('source_type')=='audio' for r in order['reviews']))
        applied_event=next(e for e in json.loads(self.request('/api/events')[2]) if e['kind']=='order_applied')
        self.assertEqual(applied_event['data']['video_source']['source_id'],p['video_source']['source_id'])


if __name__=='__main__':unittest.main()
