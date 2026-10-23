import unittest
from unittest.mock import Mock,patch
from source_gateway import GatewayError,clear_cache,fetch_page

PDF='https://grad.ajou.ac.kr/gs/community/notice.do?mode=download&articleNo=123&attachNo=456'
class PdfGatewayTests(unittest.TestCase):
    def setUp(self):clear_cache()
    def response(self,source='crawled'):
        r=Mock(status_code=200)
        r.json.return_value={'statuses':[{'id':PDF,'status':'success','source':source}], 'results':[{'url':PDF,'text':'官方附件正文与申请时间'}]}
        return r
    def test_pdf_uses_existing_key_and_requires_live_crawl(self):
        with patch.dict('os.environ',{'TRANSLATE_API_KEY':'test-key'}),patch('source_gateway.requests.post',return_value=self.response()) as post:
            self.assertIn('申请时间',fetch_page(PDF)['html'])
            self.assertEqual(fetch_page(PDF)['source'],'crawled')
        self.assertEqual(post.call_count,1)
        self.assertEqual(post.call_args.kwargs['json']['maxAgeHours'],0)
        self.assertEqual(post.call_args.kwargs['headers']['Authorization'],'Bearer test-key')
    def test_cached_pdf_cannot_be_reported_as_fresh(self):
        with patch.dict('os.environ',{'TRANSLATE_API_KEY':'test-key'}),patch('source_gateway.requests.post',return_value=self.response('cached')):
            with self.assertRaises(GatewayError):fetch_page(PDF)
    def test_untrusted_attachment_never_receives_key(self):
        with patch('source_gateway.requests.post') as post:
            with self.assertRaises(GatewayError):fetch_page('https://external.invalid/manual.pdf')
        post.assert_not_called()
    def test_authentication_error_does_not_retry_or_echo_response(self):
        with patch.dict('os.environ',{'TRANSLATE_API_KEY':'private-key'}),patch('source_gateway.requests.post',return_value=Mock(status_code=401)) as post:
            with self.assertRaisesRegex(GatewayError,'HTTP 401'):fetch_page(PDF)
        self.assertEqual(post.call_count,1)
