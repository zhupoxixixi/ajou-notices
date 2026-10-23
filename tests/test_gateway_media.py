import unittest
from unittest.mock import Mock, patch

from ai_translate import TranslationError, translate_notice,validate


class GatewayMediaTests(unittest.TestCase):
    def source(self, images):
        return {
            'id': '377708',
            'source': '中央图书馆',
            'titleKo': 'SciVal Challenge 2026',
            'published': '2026-10-20',
            'url': 'https://library.ajou.ac.kr/guide/bulletins/notice/377708',
            'body': '活动对象与详细信息见官方海报。',
            'extraText': '',
            'attachments': [],
            'images': images,
        }

    def success_response(self):
        response = Mock(status_code=200, ok=True)
        response.json.return_value = {'choices': [{'message': {'content': '{"include":false,"imagesReadable":true,"reason":"测试用排除项"}'}}]}
        return response

    def test_remote_official_image_url_is_sent_as_image_url(self):
        image_url = 'https://library.ajou.ac.kr/pyxis-api/attachments/BULLETIN/poster'
        with patch('ai_translate.requests.post', return_value=self.success_response()) as post:
            result = translate_notice(self.source([{'alt': 'official poster', 'remoteUrl': image_url}]),
                                      api_key='test-key', endpoint='https://gateway.invalid/v1', model='gpt-6-luna')
        self.assertFalse(result['include'])
        content = post.call_args.kwargs['json']['messages'][1]['content']
        self.assertEqual(content[1], {'type': 'image_url', 'image_url': {'url': image_url}})

    def test_only_first_four_remote_posters_are_sent(self):
        images = [{'remoteUrl': f'https://library.ajou.ac.kr/poster-{index}.png'} for index in range(5)]
        with patch('ai_translate.requests.post', return_value=self.success_response()) as post:
            translate_notice(self.source(images), api_key='test-key', endpoint='https://gateway.invalid/v1', model='gpt-6-luna')
        content = post.call_args.kwargs['json']['messages'][1]['content']
        image_parts = [part for part in content if part.get('type') == 'image_url']
        self.assertEqual(len(image_parts), 4)
        self.assertIn('只提供前4张海报', content[0]['text'])

    def test_remote_non_ajou_image_is_rejected_before_request(self):
        source = self.source([{'remoteUrl': 'https://images.example.com/poster.png'}])
        with patch('ai_translate.requests.post') as post:
            with self.assertRaisesRegex(TranslationError, 'Untrusted remote poster URL'):
                translate_notice(source, api_key='test-key', endpoint='https://gateway.invalid/v1', model='gpt-6-luna')
        post.assert_not_called()

    def test_non_https_image_is_rejected_before_request(self):
        source = self.source([{'remoteUrl': 'http://library.ajou.ac.kr/poster.png'}])
        with patch('ai_translate.requests.post') as post:
            with self.assertRaisesRegex(TranslationError, 'Untrusted remote poster URL'):
                translate_notice(source, api_key='test-key', endpoint='https://gateway.invalid/v1', model='gpt-6-luna')
        post.assert_not_called()

    def test_image_without_local_or_remote_data_fails_loudly(self):
        source = self.source([{'alt': 'official poster', 'url': 'https://library.ajou.ac.kr/poster.png'}])
        with patch('ai_translate.requests.post') as post:
            with self.assertRaisesRegex(TranslationError, 'Poster image data missing'):
                translate_notice(source, api_key='test-key', endpoint='https://gateway.invalid/v1', model='gpt-6-luna')
        post.assert_not_called()

    def test_unreadable_poster_cannot_be_cached_as_an_eligibility_exclusion(self):
        for flag in (None,False,'true'):
            with self.assertRaisesRegex(TranslationError,'Poster reading not confirmed'):
                validate({'include':False,'imagesReadable':flag,'reason':'图片读不到'},self.source([{'remoteUrl':'https://www.ajou.ac.kr/poster.png'}]))

    def test_complete_page_input_is_not_silently_truncated_at_four_tiles(self):
        source=self.source([{'dataUrl':'data:image/png;base64,aQ==','highDetail':True} for _ in range(6)])
        source['imageMode']='official-page-snapshot'
        with patch('ai_translate.requests.post',return_value=self.success_response()) as post:
            translate_notice(source,api_key='test-key',endpoint='https://gateway.invalid/v1')
        parts=post.call_args.kwargs['json']['messages'][1]['content']
        images=[p for p in parts if p['type']=='image_url']
        self.assertEqual(len(images),6)
        self.assertTrue(all(p['image_url']['detail']=='high' for p in images))

    def test_small_text_image_uses_explicit_high_detail(self):
        import update
        png=Mock(content=b'png',headers={'Content-Type':'image/png'})
        with patch.object(update,'binary_resource',return_value=png):
            images=update.image_evidence([{'url':'https://library.ajou.ac.kr/poster.png'}])
        with patch('ai_translate.requests.post',return_value=self.success_response()) as post:
            translate_notice(self.source(images),api_key='test-key',endpoint='https://gateway.invalid/v1')
        image=post.call_args.kwargs['json']['messages'][1]['content'][1]
        self.assertEqual(image['image_url']['detail'],'high')

    def test_wide_poster_tiles_preserve_both_edges_and_are_all_sent(self):
        import base64,io,update
        from PIL import Image
        original=Image.new('RGB',(3000,164),'white')
        original.putpixel((0,0),(255,0,0));original.putpixel((2999,163),(0,0,255))
        stream=io.BytesIO();original.save(stream,format='PNG')
        response=Mock(content=stream.getvalue(),headers={'Content-Type':'image/png'})
        with patch.object(update,'binary_resource',return_value=response):
            tiles=update.image_evidence([{'url':'https://library.ajou.ac.kr/poster.png'}])
        pictures=[Image.open(io.BytesIO(base64.b64decode(x['dataUrl'].split(',',1)[1]))) for x in tiles]
        self.assertEqual(pictures[0].getpixel((0,0)),(255,0,0))
        self.assertEqual(pictures[-1].getpixel((pictures[-1].width-1,163)),(0,0,255))
        self.assertTrue(all(x['posterTile'] for x in tiles))
        source=self.source(tiles);source['imageMode']='official-poster-tiles'
        with patch('ai_translate.requests.post',return_value=self.success_response()) as post:
            translate_notice(source,api_key='test-key',endpoint='https://gateway.invalid/v1')
        images=[x for x in post.call_args.kwargs['json']['messages'][1]['content'] if x['type']=='image_url']
        self.assertEqual(len(images),len(tiles))
        self.assertGreater(len(images),4)


if __name__ == '__main__':
    unittest.main()
