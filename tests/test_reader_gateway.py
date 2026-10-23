import unittest
from unittest.mock import Mock,patch
from crawl import article,fetch
import reader_gateway as reader
from source_gateway import GatewayError

URL='https://grad.ajou.ac.kr/gs/community/notice.do?mode=view&articleNo=123'
HTML='<html><div class="b-content-box"><p>学位论文要求</p><img src="/poster1.png"><img src="/poster2.png"><img src="/poster3.png"></div><a href="?mode=download&amp;articleNo=123&amp;attachNo=456">申请书.pdf</a></html>'
class ReaderGatewayTests(unittest.TestCase):
    def setUp(self):reader._CACHE.clear()
    def response(self,**changes):
        p={'url':URL,'httpStatus':200,'html':HTML};p.update(changes)
        r=Mock(status_code=200,content=b'html');r.json.return_value={'code':200,'data':p};return r
    def test_original_html_preserves_posters_and_attachments_without_sending_ai_key(self):
        with patch.dict('os.environ',{'TRANSLATE_API_KEY':'not-for-reader','SOURCE_TRANSPORT':'api'}),patch.object(reader,'_pace'),patch.object(reader.requests,'get',return_value=self.response()) as get:
            result=article(fetch(URL),URL)
        self.assertEqual(len(result['images']),3)
        self.assertEqual(len(result['attachments']),1)
        self.assertEqual(result['body'],'学位论文要求')
        headers=get.call_args.kwargs['headers']
        self.assertEqual(headers['X-No-Cache'],'true')
        self.assertEqual(headers['X-Respond-With'],'html')
        self.assertNotIn('Authorization',headers)
        self.assertNotIn('not-for-reader',str(get.call_args))
    def test_reader_error_page_cannot_replace_official_source(self):
        for changes in ({'httpStatus':404},{'url':'https://untrusted.invalid/'},{'html':''}):
            reader._CACHE.clear()
            with patch.object(reader,'_pace'),patch.object(reader.requests,'get',return_value=self.response(**changes)):
                with self.assertRaises(GatewayError):reader.fetch_html(URL)
    def test_unregistered_urls_are_rejected_before_network(self):
        with patch.object(reader.requests,'get') as get:
            with self.assertRaises(GatewayError):reader.fetch_html('https://www.ajou.ac.kr/login')
        get.assert_not_called()
    def test_failed_url_does_not_discard_other_successes(self):
        bad='https://grad.ajou.ac.kr/gs/community/notice.do?mode=view&articleNo=999'
        def read(url):
            if url==bad:raise GatewayError('temporary failure')
            return HTML
        with patch.object(reader,'_read',side_effect=read):results=reader.fetch_pages([URL,bad])
        self.assertEqual(results[URL],HTML)
        self.assertIsInstance(results[bad],GatewayError)
    def test_retries_transient_errors_but_preserves_final_failure(self):
        with patch.object(reader,'_pace'),patch.object(reader.time,'sleep'),patch.object(reader.requests,'get',return_value=Mock(status_code=503,headers={})) as get:
            with self.assertRaisesRegex(GatewayError,'HTTP 503'):reader.fetch_html(URL)
        self.assertEqual(get.call_count,3)
