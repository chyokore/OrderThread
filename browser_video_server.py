"""Synthetic media and mocked AI only. Uses a temporary database on port 8884."""
import base64, io, json, subprocess, tempfile
from pathlib import Path
from unittest.mock import patch
from PIL import Image, ImageDraw
import imageio_ffmpeg
from test_app import app
from test_audio import wav_audio, provider_result

with tempfile.TemporaryDirectory(prefix='orderthread-frame-browser-') as folder:
    folder=Path(folder);app.DB=folder/'browser.db'
    still=folder/'synthetic-order.png';image=Image.new('RGB',(640,360),'white');draw=ImageDraw.Draw(image)
    draw.text((30,40),'SYNTHETIC ORDER LIST',fill='black',font_size=26)
    draw.text((30,110),'10 blue zips, 20 cm',fill='blue',font_size=30)
    draw.text((30,180),'5 red zips, 20 cm',fill='red',font_size=30);image.save(still)
    video=folder/'synthetic-order.mp4'
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-loop','1','-i',str(still),'-t','4','-r','4','-c:v','libx264','-pix_fmt','yuv420p',str(video)],capture_output=True,check=True,timeout=30)
    (folder/'separate-speech.wav').write_bytes(base64.b64decode(wav_audio()['base64']))
    (folder/'invalid.mp4').write_bytes(b'This is not video data.')
    def completion(messages,provider=None):
        types=[part.get('type') for part in messages[1]['content']]
        if types==['text','image_url']:
            result={'choices':[{'message':{'content':json.dumps({'items':[{'name':'zips','quantity':10,'variant':'Blue, 20 cm','uncertain':False},{'name':'zips','quantity':5,'variant':'Red, 20 cm','uncertain':False}],'intent':'unclear','clarification':'','fulfillment_note':''})}}]}
        elif types==['text','audio_url']:result=provider_result()
        else:raise AssertionError('Unexpected AI media part; video must never be sent.')
        return result,{'provider':'baseten','model':'mock-image-or-audio-only'}
    with patch.object(app,'ai_completion',side_effect=completion),patch.dict(app.os.environ,{'BASETEN_API_KEY':'synthetic-only','AI_PROVIDER':'baseten'}):
        print('Synthetic fixture folder: '+str(folder),flush=True)
        print('Temporary mocked frame-review server: http://127.0.0.1:8884',flush=True)
        app.ThreadingHTTPServer(('127.0.0.1',8884),app.Handler).serve_forever()
