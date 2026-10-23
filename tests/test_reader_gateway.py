import unittest
from unittest.mock import Mock,patch
from crawl import article,fetch
import reader_gateway as reader
from source_gateway import GatewayError

URL='https://grad.ajou.ac.kr/gs/community/notice.do?mode=view&articleNo=123'
HTML='<html><div class="b-content-box"><p>学位论文要求</p><img src="/poster1.png"><img src="/poster2.png"><img src="/poster3.png"></div><a href="?mode=download&amp;articleNo=123&amp;attachNo=456">申请书.pdf</a></html>'
class ReaderGatewayTests(unittest.TestCase):
    def setUp(self):reader._CACHE.clear();reader._SHOTS.clear()
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
        self.assertEqual(headers['X-Respond-With'],'pageshot')
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
        for status in (422,503):
            reader._CACHE.clear()
            with patch.object(reader,'_pace'),patch.object(reader.time,'sleep'),patch.object(reader.requests,'get',return_value=Mock(status_code=status,headers={})) as get:
                with self.assertRaisesRegex(GatewayError,'HTTP '+str(status)):reader.fetch_html(URL)
            self.assertEqual(get.call_count,3)

    def test_page_image_tiles_preserve_first_and_last_rows(self):
        import io,base64
        from PIL import Image
        canvas=Image.new('RGB',(400,3501),'white')
        for x in range(400):canvas.putpixel((x,0),(255,0,0));canvas.putpixel((x,3500),(0,0,255))
        buf=io.BytesIO();canvas.save(buf,format='PNG')
        response=Mock(status_code=200,content=buf.getvalue(),headers={'Content-Type':'image/png'})
        reader._SHOTS[URL]='https://storage.googleapis.com/reader-6b7dc.appspot.com/ephemeral/image?signature=test'
        with patch.object(reader,'fetch_html'),patch.object(reader.requests,'get',return_value=response):tiles=reader.snapshot_images(URL)
        pictures=[Image.open(io.BytesIO(base64.b64decode(t['dataUrl'].split(',',1)[1]))) for t in tiles]
        self.assertGreater(len(pictures),1)
        self.assertEqual(pictures[0].getpixel((0,0)),(255,0,0))
        self.assertEqual(pictures[-1].getpixel((0,pictures[-1].height-1)),(0,0,255))
        self.assertTrue(all(t['pageSnapshot'] and t['hash'] and t['highDetail'] for t in tiles))

    def test_unverified_snapshot_url_is_rejected_before_download(self):
        reader._SHOTS[URL]='https://external.invalid/fake.png'
        with patch.object(reader,'fetch_html'),patch.object(reader.requests,'get') as get:
            with self.assertRaises(GatewayError):reader.snapshot_images(URL)
        get.assert_not_called()

    def test_snapshot_download_retries_network_and_transient_http_failures(self):
        ok=Mock(status_code=200,content=b'image',headers={'Content-Type':'image/png'})
        busy=Mock(status_code=503,headers={'Retry-After':'1'})
        with patch.object(reader.time,'sleep'),patch.object(reader.requests,'get',side_effect=[reader.requests.Timeout(),busy,ok]) as get:
            self.assertEqual(reader._download_snapshot('https://storage.googleapis.com/test'),b'image')
        self.assertEqual(get.call_count,3)

    def test_snapshot_download_preserves_permanent_failure(self):
        with patch.object(reader.requests,'get',return_value=Mock(status_code=403,headers={})) as get:
            with self.assertRaisesRegex(GatewayError,'HTTP 403'):reader._download_snapshot('https://storage.googleapis.com/test')
        self.assertEqual(get.call_count,1)

    def test_missing_snapshot_cannot_be_treated_as_readable_image(self):
        with patch.object(reader,'fetch_html'),patch.object(reader.requests,'get') as get:
            with self.assertRaisesRegex(GatewayError,'without the requested full-page image'):reader.snapshot_images(URL)
        get.assert_not_called()

    def png(self):
        import io
        from PIL import Image
        stream=io.BytesIO();Image.new('RGB',(320,100),'white').save(stream,format='PNG')
        return stream.getvalue()

    def test_prefetched_html_without_pageshot_gets_one_refresh(self):
        shot='https://storage.googleapis.com/reader-6b7dc.appspot.com/ephemeral/test?signature=test'
        responses=[self.response(),self.response(pageshotUrl=shot)]
        with patch.object(reader,'_pace'),patch.object(reader.requests,'get',side_effect=responses) as get,patch.object(reader,'_download_snapshot',return_value=self.png()):
            reader.fetch_pages([URL])
            tiles=reader.snapshot_images(URL)
        self.assertEqual(get.call_count,2)
        self.assertEqual(len(tiles),1)
        self.assertTrue(tiles[0]['hash'])

    def test_missing_pageshot_retry_is_not_cached_after_exhaustion(self):
        shot='https://storage.googleapis.com/reader-6b7dc.appspot.com/ephemeral/test?signature=test'
        responses=[self.response(),self.response(),self.response(pageshotUrl=shot)]
        with patch.object(reader,'_pace'),patch.object(reader.requests,'get',side_effect=responses) as get,patch.object(reader,'_download_snapshot',return_value=self.png()):
            reader.fetch_pages([URL])
            with self.assertRaisesRegex(GatewayError,'without the requested full-page image'):
                reader.snapshot_images(URL)
            self.assertNotIn(URL,reader._CACHE)
            self.assertNotIn(URL,reader._SHOTS)
            tiles=reader.snapshot_images(URL)
        self.assertEqual(get.call_count,3)
        self.assertEqual(len(tiles),1)
