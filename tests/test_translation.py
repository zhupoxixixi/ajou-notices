import unittest
from unittest.mock import Mock, patch

from ai_translate import TranslationError, translate_notice, valid_date, validate


class TranslationTests(unittest.TestCase):
    def source(self):
        return {
            'id': '377708',
            'source': '学校综合公告',
            'titleKo': '[중앙도서관] 연구 트렌드를 읽는 SciVal Challenge 2026',
            'body': '제출 기간: 2026. 10. 29.(목) 18:00 ~ 11. 4.(수) 24:00',
            'extraText': '',
            'images': [],
            'url': 'https://www.ajou.ac.kr/kr/ajou/notice.do?mode=view&articleNo=377708',
        }

    def test_end_of_day_24_hour_is_portable_and_normalized(self):
        payload = {
            'include': True,
            'title': 'SciVal研究趋势挑战',
            'audience': '亚洲大学研究生及活动参加者',
            'summary': '参加研究趋势培训并提交挑战结果。',
            'details': ['线上培训于10月28日至29日举行。', '挑战提交截止于11月4日24:00。'],
            'tags': ['一般大学院', '论文科研'],
            'kind': 'event',
            'eligibility': 'uncertain',
            'start': '2026-10-29T18:00',
            'end': '2026-11-04T24:00',
            'event': '2026-10-28T14:00',
            'eventEnd': '2026-10-29T24:00',
            'endEvidence': '11. 4.(수) 24:00',
            'eventEvidence': '2026. 10. 28.(수) 14:00 – 15:30; 2026. 10. 29.(목) 14:00 – 15:30',
            'note': '',
        }
        result = validate(payload, self.source())
        self.assertEqual(result['end'], '2026-11-05T00:00')
        self.assertEqual(result['eventEnd'], '2026-10-30T00:00')
        self.assertTrue(valid_date('2026-11-04T24:00'))

    def test_invalid_hour_after_24_is_rejected(self):
        self.assertFalse(valid_date('2026-11-04T24:01'))
        payload = {'include': True, 'title': '中文公告', 'audience': '研究生', 'summary': '中文摘要',
                   'details': ['第一条。', '第二条。'], 'tags': ['一般大学院'], 'kind': 'event',
                   'event': '2026-11-04T24:01'}
        with self.assertRaisesRegex(TranslationError, 'Invalid ISO date in event'):
            validate(payload, self.source())

    def test_generic_korean_title_suffix_is_translated_without_removing_names(self):
        payload = {'include': True, 'title': '모두의 BK研究活动 안내', 'audience': '研究生', 'summary': '中文摘要',
                   'details': ['第一条。', '第二条。'], 'tags': ['一般大学院'], 'kind': 'guide'}
        self.assertEqual(validate(payload, self.source())['title'], '모두의 BK研究活动通知')

    def test_validation_retry_includes_corrective_feedback(self):
        malformed = Mock(status_code=200, ok=True)
        malformed.json.return_value = {'choices': [{'message': {'content': 'not-json'}}]}
        valid = Mock(status_code=200, ok=True)
        valid.json.return_value = {'choices': [{'message': {'content': '{"include":false,"reason":"与目标读者无关"}'}}]}
        with patch('ai_translate.requests.post', side_effect=[malformed, valid]) as post, patch('ai_translate.time.sleep'):
            result = translate_notice(self.source(), api_key='test-key', endpoint='https://example.invalid/v1', model='gpt-6-luna')
        self.assertFalse(result['include'])
        self.assertEqual(post.call_count, 2)
        retry_messages = post.call_args_list[1].kwargs['json']['messages']
        self.assertIn('not-json', retry_messages[-2]['content'])
        self.assertIn('未通过程序校验', retry_messages[-1]['content'])
        self.assertEqual(post.call_args_list[0].kwargs['json']['reasoning_effort'], 'none')
        self.assertEqual(post.call_args_list[0].kwargs['json']['response_format'], {'type': 'json_object'})

    def test_http_error_exposes_provider_reason_and_request_id_without_retry(self):
        failed = Mock(status_code=400, ok=False)
        failed.headers = {'x-request-id': 'req-test-123'}
        failed.json.return_value = {'error': {'code': 'invalid_parameter', 'message': 'reasoning_effort is unsupported'}}
        with patch('ai_translate.requests.post', return_value=failed) as post:
            with self.assertRaises(TranslationError) as caught:
                translate_notice(self.source(), api_key='test-key', endpoint='https://example.invalid/v1', model='gpt-6-luna')
        message = str(caught.exception)
        self.assertIn('HTTP 400', message)
        self.assertIn('reasoning_effort is unsupported', message)
        self.assertIn('req-test-123', message)
        post.assert_called_once()


if __name__ == '__main__':
    unittest.main()
