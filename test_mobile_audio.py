"""Real codec fixtures and conversion; AI calls are always mocked."""
import base64, hashlib, io, json, subprocess, tempfile, unittest, wave
from pathlib import Path
from unittest.mock import patch
from test_audio import app, AppTests, wav_audio, provider_result

class MobileAudioTests(unittest.TestCase):
    setUp=AppTests.setUp
    tearDown=AppTests.tearDown
    request=AppTests.request

    @classmethod
    def setUpClass(cls):
        import imageio_ffmpeg
        cls.ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
        cls.fixture_folder=tempfile.TemporaryDirectory()
        cls.folder=Path(cls.fixture_folder.name)
        cls.formats={}
        for extension,mime,codec in [('m4a','audio/mp4','aac'),('aac','audio/aac','aac'),('mp3','audio/mpeg','libmp3lame'),('ogg','audio/ogg','libvorbis'),('opus','audio/ogg','libopus'),('flac','audio/flac','flac'),('webm','audio/webm','libopus')]:
            target=cls.folder/('phone.'+extension)
            subprocess.run([cls.ffmpeg,'-hide_banner','-loglevel','error','-nostdin','-f','lavfi','-i','sine=frequency=440:duration=0.5','-c:a',codec,str(target)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            cls.formats[extension]={'mime':mime,'name':target.name,'base64':base64.b64encode(target.read_bytes()).decode()}

    @classmethod
    def tearDownClass(cls):
        cls.fixture_folder.cleanup()

    def test_real_phone_formats_and_provider_wav_payload(self):
        for extension,audio in self.formats.items():
            with self.subTest(format=extension):
                with patch.object(app,'ai_completion',return_value=(provider_result(),{'provider':'baseten','model':app.MODEL})) as provider:
                    status,_,body=self.request('/api/propose-audio',{'audio':audio,'provider':'baseten'})
                self.assertEqual(status,200,body)
                data=json.loads(body);self.assertEqual(data['items'],[])
                self.assertEqual(data['source_id'],hashlib.sha256(base64.b64decode(audio['base64'])).hexdigest())
                url=provider.call_args.args[0][1]['content'][1]['audio_url']['url']
                self.assertTrue(url.startswith('data:audio/wav;base64,'))
                with wave.open(io.BytesIO(base64.b64decode(url.split(',')[1])),'rb') as decoded:
                    self.assertEqual(decoded.getframerate(),16000);self.assertEqual(decoded.getnchannels(),1)
                    self.assertGreater(decoded.getnframes(),0)
        self.assertEqual(app.events(),[])
        self.assertEqual(json.loads(self.request('/api/orders')[2]),[])

    def test_phone_mime_variants_and_wav_without_converter(self):
        for mime in ('','application/octet-stream','audio/mp4; codecs=mp4a.40.2','audio/x-m4a'):
            audio=dict(self.formats['m4a'],mime=mime)
            app.validate_audio(audio)
        app.validate_audio(dict(self.formats['webm'],mime='video/webm'))
        app.validate_audio(dict(self.formats['mp3'],name='phone.mpeg',mime='video/mpeg'))
        with patch.dict('sys.modules',{'imageio_ffmpeg':None}):
            self.assertEqual(app.validate_audio(wav_audio()),base64.b64decode(wav_audio()['base64']))
            with self.assertRaisesRegex(ValueError,'requires imageio-ffmpeg'): app.validate_audio(self.formats['m4a'])

    def test_invalid_types_size_corruption_never_call_ai(self):
        invalid=[dict(self.formats['mp3'],name='note.exe'),{'mime':'audio/mp4','base64':base64.b64encode(b'not audio').decode()},dict(self.formats['m4a'],base64='!'),dict(self.formats['m4a'],base64='A'*(4*((app.MAX_AUDIO_BYTES+2)//3)+1)),dict(self.formats['m4a'],base64='')]
        # Plausible signatures still must decode successfully.
        for extension,content in [('m4a',b'\0\0\0\x18ftypM4A '+b'\0'*20),('webm',b'\x1a\x45\xdf\xa3broken'),('ogg',b'OggSbroken')]:
            invalid.append(dict(self.formats[extension],base64=base64.b64encode(content).decode()))
        for audio in invalid:
            with self.subTest(mime=audio['mime']),patch.object(app,'ai_completion') as provider:
                status,_,body=self.request('/api/propose-audio',{'audio':audio})
                self.assertEqual(status,400,body);self.assertFalse(provider.called)
        self.assertEqual(app.events(),[])

    def test_mime_and_extension_hints_use_decoded_contents(self):
        for audio in (dict(self.formats['m4a'],mime='audio/wav'),dict(self.formats['m4a'],name='OrderThread.WAV',mime='audio/wav'),dict(self.formats['m4a'],name='OrderThread.mp3',mime='audio/mpeg')):
            with self.subTest(name=audio['name']),patch.object(app,'ai_completion',return_value=(provider_result(),{'provider':'baseten','model':app.MODEL})):
                status,_,body=self.request('/api/propose-audio',{'audio':audio,'provider':'baseten'})
            self.assertEqual(status,200,body)
            details=json.loads(body)['audio_details'];self.assertEqual(details['detected_container'],'m4a')
            self.assertTrue(details['warnings'])
            if audio['name']!='phone.m4a': self.assertIn('Renaming a file does not convert it',' '.join(details['warnings']))

    def test_mp3_complete_frames_with_small_trailer_and_corruption(self):
        target=self.folder/'six-seconds.mp3'
        subprocess.run([self.ffmpeg,'-hide_banner','-loglevel','error','-f','lavfi','-i','sine=frequency=440:duration=6','-c:a','libmp3lame','-b:a','320k',str(target)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        original=target.read_bytes();with_trailer=original+b'non-audio trailer'*50
        self.assertEqual(app.trim_mp3_trailer(with_trailer),original)
        audio={'mime':'audio/wav','name':'OrderThread.WAV','base64':base64.b64encode(with_trailer).decode()}
        decoded,details=app.prepare_audio(audio)
        self.assertTrue(any('non-audio' in warning for warning in details['warnings']))
        with wave.open(io.BytesIO(decoded)) as w: self.assertTrue(5.9<w.getnframes()/w.getframerate()<6.2)
        # Do not disguise an incomplete last frame or internal corruption as a trailer.
        truncated=original[:-20]
        with self.assertRaisesRegex(ValueError,'incomplete'): app.trim_mp3_trailer(truncated)
        corrupt=original[:1000]+b'broken'*10000+original[1000:]
        with patch.object(app,'ai_completion') as provider:
            status,_,_=self.request('/api/propose-audio',{'audio':dict(audio,base64=base64.b64encode(corrupt).decode())})
            self.assertEqual(status,400);self.assertFalse(provider.called)
        oversized=original+b'junk'*2000
        with self.assertRaisesRegex(ValueError,'trailer'): app.trim_mp3_trailer(oversized)

    def test_real_duration_limit_rejects_without_truncation(self):
        target=self.folder/'long.m4a'
        subprocess.run([self.ffmpeg,'-hide_banner','-loglevel','error','-f','lavfi','-i','sine=frequency=440:duration=65','-c:a','aac',str(target)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        audio={'mime':'audio/mp4','name':'long.m4a','base64':base64.b64encode(target.read_bytes()).decode()}
        with patch.object(app,'ai_completion') as provider:
            status,_,body=self.request('/api/propose-audio',{'audio':audio})
            self.assertEqual(status,400);self.assertIn('60 seconds',body);self.assertFalse(provider.called)

    def test_conversion_failure_timeout_and_cleanup_are_safe(self):
        created=[]
        def failure(command,**kwargs):
            created.append(Path(command[-1]).parent)
            return subprocess.CompletedProcess(command,1)
        for effect,expected in [(failure,'decoded or converted'),(subprocess.TimeoutExpired('private-path',30),'timed out'),(OSError('sensitive internal details'),'decoded or converted')]:
            with patch.object(app.subprocess,'run',side_effect=effect),patch.object(app,'ai_completion') as provider:
                status,_,body=self.request('/api/propose-audio',{'audio':self.formats['m4a']})
                self.assertEqual(status,400);self.assertIn(expected,body);self.assertNotIn('sensitive',body);self.assertNotIn('private-path',body);self.assertFalse(provider.called)
        self.assertTrue(all(not path.exists() for path in created))
        def corrupt_output(command,**kwargs):
            Path(command[-1]).write_bytes(b'not wav')
            return subprocess.CompletedProcess(command,0)
        with patch.object(app.subprocess,'run',side_effect=corrupt_output):
            with self.assertRaisesRegex(ValueError,'readable audio'): app.validate_audio(self.formats['m4a'])

if __name__=='__main__': unittest.main()
