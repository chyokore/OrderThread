import unittest,urllib.request
from test_app import AppTests,app

class StartupTests(unittest.TestCase):
    setUp=AppTests.setUp
    tearDown=AppTests.tearDown
    request=AppTests.request
    def test_static_recorder_and_provider_contract(self):
        status,headers,page=self.request('/')
        self.assertEqual(status,200);self.assertEqual(headers['Cache-Control'],'no-store')
        self.assertIn('typeof window.OrderThreadVoiceRecorder',page)
        self.assertIn('File upload is still available',page)
        status,headers,script=self.request('/recorder.js');self.assertEqual(status,200);self.assertIn('javascript',headers['Content-Type']);self.assertIn('OrderThreadVoiceRecorder',script)
        import json
        self.assertEqual([p['id'] for p in json.loads(self.request('/api/status')[2])['providers']],['baseten','meta'])
    @unittest.skipUnless(app.os.name=='nt','Windows exclusive binding regression')
    def test_second_listener_cannot_share_existing_port(self):
        with self.assertRaises(OSError): app.ThreadingHTTPServer(('127.0.0.1',self.server.server_port),app.Handler)

if __name__=='__main__':unittest.main()
