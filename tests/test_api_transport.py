import unittest
from unittest.mock import patch

import update


class ApiTransportTests(unittest.TestCase):
    def setUp(self):
        self.source={'id':'1','board':'graduate','source':'一般大学院','titleKo':'대학원 공지','published':'2026-10-15','url':'https://grad.ajou.ac.kr/gs/community/notice.do?mode=view&articleNo=1','attachments':[],'images':[],'body':'신청기간: 2026.10.15 ~ 2026.10.21','extraText':''}
        self.decision={'include':True,'title':'研究生申请','audience':'研究生','summary':'提交申请','details':['准备材料。','按时提交。'],'tags':['一般大学院'],'kind':'deadline','start':'2026-10-15','end':'2026-10-21','event':None,'endEvidence':'2026.10.21','note':''}
        self.now='2026-10-23T18:00:00+09:00'

    def test_api_mode_sends_official_poster_to_gateway_without_direct_download(self):
        image={'url':'https://www.ajou.ac.kr/poster.png','alt':''}
        with patch.dict('os.environ',{'SOURCE_TRANSPORT':'api'}),patch.object(update,'binary_resource') as download:
            result=update.image_evidence([image])
        download.assert_not_called()
        self.assertEqual(result[0]['remoteUrl'],image['url'])
        self.assertNotIn('hash',result[0])

    def test_remote_poster_does_not_reuse_an_exclusion_with_same_url(self):
        image={'url':'https://www.ajou.ac.kr/poster.png','remoteUrl':'https://www.ajou.ac.kr/poster.png'}
        self.source['images']=[image]
        with patch.dict('os.environ',{'SOURCE_CACHE_MINUTES':'0'}),patch.object(update,'source_for',return_value=self.source),patch.object(update,'image_evidence',return_value=[image]),patch.object(update,'translate_notice',return_value={'include':False,'reason':'仅限本科生'}) as api:
            _,state,_=update.process(self.source,None,None,None,'gpt-6-luna',self.now)
            update.process(self.source,None,state,None,'gpt-6-luna',self.now)
        self.assertEqual(api.call_count,2)

    def test_remote_poster_is_rechecked_even_with_human_seed_fingerprint(self):
        image={'url':'https://www.ajou.ac.kr/poster.png','remoteUrl':'https://www.ajou.ac.kr/poster.png'}
        self.source['images']=[image]
        seed={**self.source,**self.decision,'reviewedFingerprint':update.base_fingerprint(self.source)}
        with patch.dict('os.environ',{'SOURCE_CACHE_MINUTES':'0'}),patch.object(update,'source_for',return_value=self.source),patch.object(update,'image_evidence',return_value=[image]),patch.object(update,'translate_notice',return_value=self.decision) as api:
            result,_,action=update.process(self.source,seed,None,seed,'gpt-6-luna',self.now)
        api.assert_called_once()
        self.assertEqual(action,'translated')
        self.assertEqual(result['editorial'],'auto')

    def test_different_poster_bytes_invalidate_exclusion(self):
        state=None
        with patch.dict('os.environ',{'SOURCE_CACHE_MINUTES':'0'}),patch.object(update,'source_for',return_value=self.source),patch.object(update,'image_evidence',side_effect=[[{'hash':'old'}],[{'hash':'new'}]]),patch.object(update,'translate_notice',return_value={'include':False,'reason':'仅限本科生'}) as api:
            _,state,_=update.process(self.source,None,state,None,'gpt-6-luna',self.now)
            update.process(self.source,None,state,None,'gpt-6-luna',self.now)
        self.assertEqual(api.call_count,2)

    def test_transport_change_invalidates_short_source_cache(self):
        state={'model':'gpt-6-luna','checkedAt':self.now}
        with patch.dict('os.environ',{'SOURCE_CACHE_MINUTES':'30','SOURCE_TRANSPORT':'api'}):
            self.assertFalse(update.cached_source(None,state,'gpt-6-luna',self.now))
            self.assertTrue(update.cached_source(None,{**state,'transport':'api'},'gpt-6-luna',self.now))


if __name__=='__main__':unittest.main()
