import datetime as dt
import json
import unittest
from unittest.mock import Mock,patch
from crawl import BOARDS,listing,scan_board
from public_sources import calendar_rows
from calendar_export import events_for,calendar
from delivery import changes,notify,fingerprint,healthy,heartbeat
from update import source_for

class SourceTests(unittest.TestCase):
    def test_display_expiry_is_not_publication(self):
        html='<table><thead>공지마감일</thead><tr><td><a href="?mode=view&articleNo=1">학위논문</a></td><td class="b-date">2027-01-15</td></tr></table>'
        row=listing(html,BOARDS['graduate'][1],'graduate')[0]
        self.assertEqual(row['published'],'');self.assertEqual(row['displayUntil'],'2027-01-15')
    def test_request_limit_is_visible(self):
        def fetcher(url):
            page=int(url.split('article.offset=')[1])
            return '<table>'+''.join(f'<tr><td><a href="?mode=view&articleNo={page+i}">연구 {i}</a></td><td class="b-date">2026-10-16</td></tr>' for i in range(10))+'</table>'
        rows,state=scan_board('graduate',set(),dt.date(2026,10,16),fetcher=fetcher,max_pages=2)
        self.assertEqual(len(rows),20);self.assertTrue(state['bounded'])
    def test_calendar_vague_dates_and_next_year(self):
        html='<h4>2026학년도</h4><table class="ajou-gs-table"><tr><td>2학기</td><td>논문 제출</td><td>1.8.(금) ~ 1.15.(금)</td><td></td></tr><tr><td>학과 상담</td><td>10월 중</td><td></td></tr></table>'
        rows=calendar_rows(html)
        self.assertEqual(rows[0]['calendarEnd'],'2027-01-15');self.assertIsNone(rows[1]['calendarEnd'])
    def test_calendar_same_title_in_two_semesters_has_distinct_identity(self):
        html='<h4>2026학년도</h4><table class="ajou-gs-table"><tr><td>1학기</td><td>논문 제출</td><td>6.1.(월)</td><td></td></tr><tr><td>2학기</td><td>논문 제출</td><td>12.1.(화)</td><td></td></tr></table>'
        rows=calendar_rows(html);self.assertNotEqual(rows[0]['id'],rows[1]['id'])
    def test_library_detail_route_and_blob_fallback(self):
        row={'id':'library-23188','board':'library','url':'https://library.ajou.ac.kr/guide/bulletins/notice/23188'}
        data={'success':True,'data':{'dateCreated':'2026-10-15 09:19','content':'<p>研究资料培训</p><img src="blob:missing">'}}
        with patch('update.fetch',return_value=json.dumps(data)) as get:
            result=source_for(row,None)
        self.assertEqual(get.call_args.args[0],'https://library.ajou.ac.kr/pyxis-api/1/bulletins/23188?includeContent=true')
        self.assertEqual(result['unreadableImages'],1);self.assertEqual(result['images'],[]);self.assertIn('研究',result['body'])

class CalendarTests(unittest.TestCase):
    def item(self):
        return {'id':'sample','title':'论文,提交;事项','url':'https://grad.ajou.ac.kr/','audience':'研究生','summary':'请按时提交','editorial':'auto','kind':'deadline','end':'2026-10-16','endEvidence':'10.16','translatedAt':'2026-10-15T10:00:00+09:00'}
    def test_all_day_end_is_exclusive_and_uid_stable(self):
        a=self.item();first=calendar(events_for(a,'2026-10-15'));a['end']='2026-10-20';second=calendar(events_for(a,'2026-10-16'))
        self.assertIn('DTEND;VALUE=DATE:20261017',first)
        self.assertEqual([x for x in first.splitlines() if x.startswith('UID:')],[x for x in second.splitlines() if x.startswith('UID:')])
        self.assertIn('论文\\,提交\\;事项',first)
    def test_precise_kst_becomes_utc_without_invented_time(self):
        a=self.item();a['end']='2026-10-16T18:00'
        self.assertIn('DTSTART:20261016T090000Z',calendar(events_for(a,'2026-10-15')))
    def test_unknown_qualification_and_changed_source_not_exported(self):
        for extra in [{'eligibility':'uncertain'},{'reviewNeeded':True},{'endEvidence':''}]:
            self.assertEqual(events_for({**self.item(),**extra},'2026-10-15'),[])
    def test_utf8_lines_obey_calendar_byte_limit(self):
        a=self.item();a['summary']='中文摘要'*100
        for line in calendar(events_for(a,'2026-10-15')).split('\r\n'):self.assertLessEqual(len(line.encode()),75)

class DeliveryTests(unittest.TestCase):
    def test_first_run_is_silent_then_only_semantic_changes(self):
        a=CalendarTests().item();client=Mock();data={'items':[a]}
        state,count=notify(data,{},topic='test',client=client)
        self.assertEqual(count,0);client.post.assert_not_called()
        self.assertEqual(changes({'items':[{**a,'lastCheckedAt':'tomorrow'}]},state),[])
        self.assertEqual(len(changes({'items':[{**a,'end':'2026-10-20'}]},state)),1)
    def test_failed_delivery_does_not_advance_receipt(self):
        a=CalendarTests().item();state={'initialized':True,'items':{}};client=Mock();client.post.side_effect=RuntimeError('failed')
        with self.assertRaises(RuntimeError):notify({'items':[a]},state,topic='test',client=client)
        self.assertEqual(state['items'],{})
    def test_partial_data_cannot_report_complete_health(self):
        self.assertFalse(healthy({'sources':[{'status':'partial'}]}))
        self.assertFalse(healthy({'sources':[{'status':'ok'}],'pending':[{'id':'x'}]}))
    def test_failure_heartbeat_uses_fail_endpoint(self):
        client=Mock();heartbeat('https://hc-ping.com/test',False,client=client)
        self.assertEqual(client.post.call_args.args[0],'https://hc-ping.com/test/fail')

if __name__=='__main__':unittest.main()
