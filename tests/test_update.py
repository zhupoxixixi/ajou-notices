import datetime as dt, json, os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import update
from ai_translate import validate, TranslationError

class UpdateTests(unittest.TestCase):
    def notice(self):
        return {'id':'1','board':'graduate','source':'一般大学院','titleKo':'대학원 공지','published':'2026-10-15','url':'https://grad.ajou.ac.kr/gs/community/notice.do?mode=view&articleNo=1','attachments':[],'images':[],'body':'신청기간: 2026.10.15 ~ 2026.10.21','extraText':''}
    def decision(self):
        return {'include':True,'title':'研究生申请','audience':'研究生','summary':'提交申请','details':['准备材料。','按时提交。'],'tags':['一般大学院'],'kind':'deadline','start':'2026-10-15','end':'2026-10-21','event':None,'endEvidence':'2026.10.21','note':''}
    def test_date_requires_actual_source_quote(self):
        s=self.notice();r=self.decision();self.assertTrue(validate(r,s)['include'])
        r['endEvidence']='2026.12.31'
        with self.assertRaises(TranslationError):validate(r,s)
    def test_bad_dates_cannot_be_published(self):
        r=self.decision();r['end']='2026-02-30'
        with self.assertRaises(TranslationError):validate(r,self.notice())
    def test_undergraduate_exclusion_contract(self):
        self.assertEqual(validate({'include':False,'reason':'仅限本科生'},self.notice())['include'],False)
    def test_ineligible_chinese_applicants_cannot_remain_included(self):
        result=self.decision();result['note']='限ASEAN成员国，中国公民不符合。'
        self.assertFalse(validate(result,self.notice())['include'])
    def test_conflicting_original_dates_are_not_guessed(self):
        result=self.decision();result['start']='2026-07-13';result['end']='2026-01-17'
        normalized=validate(result,self.notice());self.assertIsNone(normalized['end']);self.assertIn('冲突',normalized['note'])
    def test_same_day_reverse_times_are_not_guessed(self):
        result=self.decision();result.update(start='2026-10-21T18:00',end='2026-10-21T09:00')
        self.assertIsNone(validate(result,self.notice())['end'])
    def test_embedded_poster_data_is_supported_without_network(self):
        import base64
        body=b'image-test-content';url='data:image/jpeg;base64,'+base64.b64encode(body).decode()
        with patch.object(update.requests,'get') as net:
            result=update.image_evidence([{'url':url,'alt':''}])
        net.assert_not_called();self.assertEqual(result[0]['dataUrl'],url)
    def test_unchanged_human_translation_never_calls_api(self):
        source=self.notice();seed={**source,**self.decision(),'reviewedFingerprint':update.base_fingerprint(source)}
        with patch.object(update,'source_for',return_value=source),patch.object(update,'image_evidence',return_value=[]),patch.object(update,'translate_notice') as api:
            result,state,action=update.process(source,seed,None,seed,'gpt-6-luna','2026-10-15T12:00:00+09:00')
        self.assertEqual(action,'unchanged');self.assertEqual(result['editorial'],'human');api.assert_not_called()
    def test_new_notice_uses_translated_fields_but_original_url(self):
        source=self.notice()
        with patch.object(update,'source_for',return_value=source),patch.object(update,'image_evidence',return_value=[]),patch.object(update,'translate_notice',return_value=self.decision()):
            result,state,action=update.process(source,None,None,None,'gpt-6-luna','2026-10-15T12:00:00+09:00')
        self.assertEqual(result['translationModel'],'gpt-6-luna');self.assertEqual(result['url'],source['url']);self.assertEqual(result['editorial'],'auto')
    def test_api_failure_does_not_mutate_previous_item(self):
        source=self.notice();prior={'summary':'之前的中文','id':'1'}
        with patch.object(update,'source_for',return_value=source),patch.object(update,'image_evidence',return_value=[]),patch.object(update,'translate_notice',side_effect=TranslationError('HTTP 429')):
            with self.assertRaises(TranslationError):update.process(source,prior,None,None,'gpt-6-luna','2026-10-15T12:00:00+09:00')
        self.assertEqual(prior,{'summary':'之前的中文','id':'1'})
    def test_general_university_undergrad_noise_not_a_candidate(self):
        row={**self.notice(),'id':'3','board':'university','titleKo':'[학부] 수강신청'}
        self.assertFalse(update.candidate(row,set(),dt.date(2026,10,15)))
    def test_old_pinned_guide_remains_candidate(self):
        row={**self.notice(),'published':'2022-05-12','pinned':True}
        self.assertTrue(update.candidate(row,set(),dt.date(2026,10,15)))
    def test_successful_exclusions_are_persisted_as_source_checks(self):
        source=self.notice()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'data').mkdir()
            (root/'data'/'seed.json').write_text(json.dumps({'items':[],'exclusions':[]}),encoding='utf8')
            patches=(
                patch.object(update,'ROOT',root),
                patch.object(update,'BOARDS',{
                    'graduate':('一般大学院','https://grad.ajou.ac.kr/gs/community/notice.do'),
                    'university':('学校公告','https://www.ajou.ac.kr/kr/ajou/notice.do'),
                    'oia':('国际处','https://www.ajou.ac.kr/oia/notice.do'),
                }),
                patch.object(update,'scan_board',side_effect=lambda board,*_: (
                    [source] if board=='graduate' else [],
                    {'key':board,'status':'ok','pages':1,'error':None},
                )),
                patch.object(update,'source_for',return_value={**source,'extraText':'','body':'official text','images':[],'attachments':[]}),
                patch.object(update,'image_evidence',return_value=[]),
                patch.object(update,'translate_notice',return_value={'include':False,'reason':'不符合收录范围'}),
                patch.dict(os.environ,{'TRANSLATE_API_KEY':'test-placeholder','SOURCE_TRANSPORT':'direct','SOURCE_CACHE_MINUTES':'0'}),
            )
            with patches[0],patches[1],patches[2],patches[3],patches[4],patches[5],patches[6]:
                archive=update.run()
            state=json.loads((root/'data'/'state.json').read_text(encoding='utf8'))
            stats=json.loads((root/'data'/'update.json').read_text(encoding='utf8'))
        self.assertIn(source['id'],state)
        self.assertEqual(state[source['id']]['reason'],'不符合收录范围')
        self.assertEqual(stats['excluded'],1)
        self.assertEqual(archive['updateStats']['excluded'],1)
    def test_successful_empty_board_scans_are_recorded(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'data').mkdir()
            (root/'data'/'seed.json').write_text(json.dumps({'items':[],'exclusions':[]}),encoding='utf8')
            boards={
                'graduate':('一般大学院','https://grad.ajou.ac.kr/gs/community/notice.do'),
                'university':('学校公告','https://www.ajou.ac.kr/kr/ajou/notice.do'),
                'oia':('国际处','https://www.ajou.ac.kr/oia/notice.do'),
            }
            def empty_scan(board,*_):
                return [],{'key':board,'status':'ok','pages':1,'error':None}
            patches=(
                patch.object(update,'ROOT',root),
                patch.object(update,'BOARDS',boards),
                patch.object(update,'scan_board',side_effect=empty_scan),
                patch.dict(os.environ,{'TRANSLATE_API_KEY':'test-placeholder','SOURCE_TRANSPORT':'direct','SOURCE_CACHE_MINUTES':'0'}),
            )
            with patches[0],patches[1],patches[2],patches[3]:
                archive=update.run()
            stats=json.loads((root/'data'/'update.json').read_text(encoding='utf8'))
        self.assertEqual(stats['boards'],3)
        self.assertEqual(stats['scanned'],0)
        self.assertEqual(len(archive['items']),0)
class ResourceRecoveryTests(unittest.TestCase):
    def test_library_embedded_public_body_does_not_require_broken_detail_route(self):
        row={'id':'library-23063','board':'library','url':'https://library.ajou.ac.kr/guide/bulletins/notice/23063',
             'body':'公开列表提供的论文培训正文','images':[],'attachments':[]}
        with patch.object(update,'fetch',side_effect=AssertionError('Detail route must not be called')):
            result=update.source_for(row,None)
        self.assertEqual(result['body'],row['body'])
        self.assertEqual(result['extraText'],'')
    def test_posters_use_retrying_thread_local_connection(self):
        from unittest.mock import Mock
        client=Mock();response=Mock();response.content=b'poster';response.headers={'Content-Type':'image/png'};client.get.return_value=response
        with patch.object(update,'session',return_value=client):
            result=update.image_evidence([{'url':'https://www.ajou.ac.kr/poster.png','alt':''}])
        client.get.assert_called_once();response.raise_for_status.assert_called_once()
        self.assertTrue(result[0]['dataUrl'].startswith('data:image/png;base64,'))
    def test_scanned_pdf_page_numbers_are_not_treated_as_prose(self):
        import io
        from pypdf import PdfWriter
        from unittest.mock import Mock
        writer=PdfWriter();writer.add_blank_page(width=100,height=100);stream=io.BytesIO();writer.write(stream)
        response=Mock();response.content=stream.getvalue()
        html='<div class="b-content-box"></div><a href="?mode=file-download&amp;attachNo=1">manual.pdf</a>'
        row={'id':'scan','board':'scholarship','url':'https://www.ajou.ac.kr/kr/ajou/notice_scholarship.do?mode=view&articleNo=scan'}
        with patch.object(update,'fetch',return_value=html),patch.object(update,'binary_resource',return_value=response):
            source=update.source_for(row,None)
        self.assertEqual(source['body'],'')
        self.assertIn('扫描件',source['unavailableReason'])
    def test_unreadable_content_is_retried_not_cached_as_an_exclusion(self):
        self.assertTrue(update.needs_source_retry({'action':'skipped','reason':'unknown content problem'}))
        self.assertTrue(update.needs_source_retry({'reason':'PDF为扫描件，未取得可核验正文'}))
        self.assertFalse(update.needs_source_retry({'reason':'仅限韩国籍'}))
    def test_oversized_download_is_not_accepted(self):
        from unittest.mock import Mock
        client=Mock();client.get.return_value.content=b'1234'
        with patch.object(update,'session',return_value=client),self.assertRaises(ValueError):
            update.binary_resource('https://www.ajou.ac.kr/file.pdf',3)

if __name__=='__main__':unittest.main()
