import unittest, io, copy, json, tempfile, os
from unittest.mock import patch, Mock
from PIL import Image
from pathlib import Path

import update


class ApiTransportTests(unittest.TestCase):
    def setUp(self):
        self.source={'id':'1','board':'graduate','source':'一般大学院','titleKo':'대학원 공지','published':'2026-10-15','url':'https://grad.ajou.ac.kr/gs/community/notice.do?mode=view&articleNo=1','attachments':[],'images':[],'body':'신청기간: 2026.10.15 ~ 2026.10.21','extraText':''}
        self.decision={'include':True,'title':'研究生申请','audience':'研究生','summary':'提交申请','details':['准备材料。','按时提交。'],'tags':['一般大学院'],'kind':'deadline','start':'2026-10-15','end':'2026-10-21','event':None,'endEvidence':'2026.10.21','note':''}
        self.now='2026-10-23T18:00:00+09:00'

    def test_api_mode_falls_back_to_full_page_if_image_proxy_fails(self):
        image={'url':'https://www.ajou.ac.kr/poster.png','alt':''}
        with patch.dict('os.environ',{'SOURCE_TRANSPORT':'api'}),patch.object(update,'binary_resource') as download,patch.object(update.requests,'get',side_effect=update.requests.Timeout()),patch('reader_gateway.snapshot_images',return_value=[{'pageSnapshot':True,'hash':'pixels','dataUrl':'data:image/png;base64,aQ=='}]) as snapshot:
            result=update.image_evidence([image],page_url=self.source['url'])
        download.assert_not_called()
        snapshot.assert_called_once_with(self.source['url'])
        self.assertTrue(result[0]['pageSnapshot'])
        self.assertEqual(result[0]['hash'],'pixels')

    def test_poster_content_not_page_chrome_drives_translation(self):
        def png(color):
            out=io.BytesIO();Image.new('RGB',(320,200),color).save(out,format='PNG');return out.getvalue()
        original,changed=png('white'),png('black')
        response=Mock(content=original,headers={'Content-Type':'image/png'})
        self.source['images']=[{'url':'https://www.ajou.ac.kr/poster.png','alt':''}]
        with patch.dict('os.environ',{'SOURCE_TRANSPORT':'api','SOURCE_CACHE_MINUTES':'0'}),patch.object(update,'source_for',side_effect=lambda *_:copy.deepcopy(self.source)),patch.object(update.requests,'get',return_value=response) as get,patch.object(update,'translate_notice',return_value=self.decision) as translate:
            prior,state,action=update.process(self.source,None,None,None,'gpt-6-luna',self.now)
            self.assertEqual(action,'translated')
            _,state,action=update.process(self.source,prior,state,None,'gpt-6-luna',self.now)
            self.assertEqual(action,'unchanged')
            self.assertEqual(translate.call_count,1)
            response.content=changed
            _,_,action=update.process(self.source,prior,state,None,'gpt-6-luna',self.now)
        self.assertEqual(action,'translated')
        self.assertEqual(translate.call_count,2)
        self.assertEqual(get.call_count,3)
        self.assertNotIn('Authorization',get.call_args.kwargs['headers'])

    def test_proxy_outage_does_not_turn_stable_poster_into_new_translation(self):
        from source_gateway import GatewayError
        self.source['images']=[{'url':'https://www.ajou.ac.kr/poster.png','alt':''}]
        prior={'id':'1','summary':'旧摘要'}
        state={'fingerprintKind':'posters','sourceFingerprint':update.base_fingerprint(self.source)}
        snapshot=[{'pageSnapshot':True,'hash':'page-with-new-counter'}]
        with patch.object(update,'source_for',side_effect=lambda *_:copy.deepcopy(self.source)),patch.object(update,'image_evidence',return_value=snapshot),patch.object(update,'translate_notice') as translate:
            with self.assertRaisesRegex(GatewayError,'retaining previous result'):
                update.process(self.source,prior,state,None,'gpt-6-luna',self.now)
        translate.assert_not_called()

    def test_two_refreshes_persist_and_reuse_poster_fingerprint(self):
        out=io.BytesIO();Image.new('RGB',(320,200),'white').save(out,format='PNG')
        response=Mock(content=out.getvalue(),headers={'Content-Type':'image/png'})
        source=copy.deepcopy(self.source)
        source['images']=[{'url':'https://www.ajou.ac.kr/poster.png','alt':''}]
        boards={key:(key,'https://grad.ajou.ac.kr/gs/community/notice.do') for key in ('graduate','university','oia')}
        def scan(board,*_):
            return ([source] if board=='graduate' else []),{'key':board,'status':'ok','pages':1,'error':None}
        temp_root=update.ROOT/'output'/'luna-usage-investigation-20261105'
        temp_root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_root) as directory:
            root=Path(directory);(root/'data').mkdir()
            (root/'data'/'seed.json').write_text(json.dumps({'items':[],'exclusions':[]}),encoding='utf8')
            with patch.object(update,'ROOT',root),patch.object(update,'BOARDS',boards),patch.object(update,'scan_board',side_effect=scan),patch.object(update,'source_for',side_effect=lambda *_:copy.deepcopy(source)),patch.object(update.requests,'get',return_value=response),patch('reader_gateway.fetch_pages'),patch.object(update,'translate_notice',return_value=self.decision) as translate,patch.dict(os.environ,{'TRANSLATE_API_KEY':'test-placeholder','SOURCE_TRANSPORT':'api','SOURCE_CACHE_MINUTES':'0'}):
                first=update.run()
                second=update.run()
            state=json.loads((root/'data'/'state.json').read_text(encoding='utf8'))
        self.assertEqual(first['updateStats']['translated'],1)
        self.assertEqual(second['updateStats']['unchanged'],1)
        self.assertEqual(translate.call_count,1)
        self.assertEqual(state['1']['fingerprintKind'],'posters')

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

    def test_identical_hashed_page_snapshot_reuses_exclusion_after_refetch(self):
        image={'pageSnapshot':True,'hash':'same-pixels','dataUrl':'data:image/png;base64,aQ==','highDetail':True}
        self.source['images']=[image]
        with patch.dict('os.environ',{'SOURCE_CACHE_MINUTES':'0'}),patch.object(update,'source_for',return_value=self.source) as source_for,patch.object(update,'image_evidence',return_value=[image]) as evidence,patch.object(update,'translate_notice',return_value={'include':False,'reason':'仅限本科生'}) as api:
            _,state,_=update.process(self.source,None,None,None,'gpt-6-luna',self.now)
            update.process(self.source,None,state,None,'gpt-6-luna',self.now)
        self.assertEqual(source_for.call_count,2)
        self.assertEqual(evidence.call_count,2)
        self.assertEqual(api.call_count,1)

    def test_hashed_page_snapshot_does_not_bypass_unverified_human_seed(self):
        image={'pageSnapshot':True,'hash':'pixels','dataUrl':'data:image/png;base64,aQ==','highDetail':True}
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
        state={'model':'gpt-6-luna','prompt':update.PROMPT_VERSION,'checkedAt':self.now}
        with patch.dict('os.environ',{'SOURCE_CACHE_MINUTES':'30','SOURCE_TRANSPORT':'api'}):
            self.assertFalse(update.cached_source(None,state,'gpt-6-luna',self.now))
            self.assertTrue(update.cached_source(None,{**state,'transport':'api'},'gpt-6-luna',self.now))

    def test_prompt_change_does_not_reuse_recent_source_decision(self):
        state={'model':'gpt-6-luna','transport':'api','checkedAt':self.now,'prompt':update.PROMPT_VERSION-1}
        with patch.dict('os.environ',{'SOURCE_CACHE_MINUTES':'30','SOURCE_TRANSPORT':'api'}):
            self.assertFalse(update.cached_source(None,state,'gpt-6-luna',self.now))
            self.assertFalse(update.cached_source(None,{k:v for k,v in state.items() if k!='prompt'},'gpt-6-luna',self.now))


if __name__=='__main__':unittest.main()
