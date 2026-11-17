"""NTIS R&D 공고 RSS 수집: 해석, 날짜·금액 변환, 공고현황, 링크 기준 누적 보관, 실패 시 기존 파일 유지를 확인합니다(네트워크 없음)."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import rnd_collector as rc

# 실제 NTIS 응답(2026-11-17)과 같은 형식. pubDate는 점 구분, rNum·totCnt는 안내 자료에 없는 추가 항목입니다.
SAMPLE = '''<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>R&amp;D 신규사업공고</title>
<link>https://www.ntis.go.kr/rndgate/eg/un/ra/mng.do</link>
<item><title>「K-문샷 휴머노이드 미션 달성을 위한 신규 R&amp;D 사업 기획 연구」 정책연구과제 공고</title>
<link>https://www.ntis.go.kr/rndgate/eg/un/ra/view.do?roRndUid=1282959</link><author>과학기술정보통신부</author>
<category>국가과학기술연구회</category><pubDate>2026.11.13</pubDate><rNum>1</rNum><totCnt>10410</totCnt>
<appbegin>2026-11-13</appbegin><appdue>2026-11-23</appdue><budget>120000000</budget></item>
<item><title>2027년 스마트팜 실증 사업 공고</title>
<link>https://www.ntis.go.kr/rndgate/eg/un/ra/view.do?roRndUid=1282000</link><author>농림축산식품부</author>
<category>농림식품기술기획평가원</category><pubDate>2026.11.12</pubDate>
<appbegin>2026-12-01</appbegin><appdue>2026-12-20</appdue><budget></budget></item>
<item><title>링크가 NTIS가 아닌 항목</title><link>https://example.com/x</link></item>
</channel></rss>'''.encode('utf-8')

NOW = datetime(2026, 11, 17, 3, 0, tzinfo=timezone.utc)  # 한국 시간 2026-11-17 12:00


class ParseTest(unittest.TestCase):
    def test_parses_ntis_fields(self):
        items = rc.parse_feed(SAMPLE)
        self.assertEqual(len(items), 2)  # NTIS 외부 링크는 제외
        first = items[0]
        self.assertEqual(first['id'], 'ntis-1282959')
        self.assertEqual(first['ministry'], '과학기술정보통신부')
        self.assertEqual(first['agency'], '국가과학기술연구회')
        self.assertEqual(first['posted_date'], '2026-11-13')
        self.assertEqual((first['open_date'], first['close_date']), ('2026-11-13', '2026-11-23'))
        self.assertEqual(first['budget_won'], 120000000)
        self.assertIn('R&D', first['title'])
        self.assertIsNone(items[1]['budget_won'])

    def test_rejects_dtd_and_non_rss(self):
        with self.assertRaises(ValueError):
            rc.parse_feed(b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><rss><channel/></rss>')
        with self.assertRaises(ValueError):
            rc.parse_feed(b'<html><body>error</body></html>')

    def test_date_and_budget_helpers(self):
        self.assertEqual(rc.iso_date('2026.11.13'), '2026-11-13')
        self.assertEqual(rc.iso_date('20200311'), '2020-03-11')
        self.assertEqual(rc.iso_date('2026-02-30'), '')
        self.assertEqual(rc.iso_date(''), '')
        self.assertEqual(rc.budget_won('1,500,000,000'), 1500000000)
        self.assertIsNone(rc.budget_won(''))

    def test_status_from_dates(self):
        today = '2026-11-17'
        self.assertEqual(rc.announcement_status('2026-11-13', '2026-11-23', today), '접수중')
        self.assertEqual(rc.announcement_status('2026-11-13', '2026-11-17', today), '접수중')  # 마감 당일
        self.assertEqual(rc.announcement_status('2026-12-01', '2026-12-20', today), '접수예정')
        self.assertEqual(rc.announcement_status('2026-10-01', '2026-11-16', today), '마감')
        self.assertEqual(rc.announcement_status('', '', today), '')


class MergeTest(unittest.TestCase):
    def test_same_link_saved_once_and_accumulates(self):
        first, added = rc.build({}, rc.parse_feed(SAMPLE), NOW)
        self.assertEqual((len(first['items']), added), (2, 2))
        # 다음 수집: 한 건은 그대로(마감일 변경), 한 건은 RSS에서 빠지고, 새 공고 한 건 추가
        changed = [dict(rc.parse_feed(SAMPLE)[0], close_date='2026-11-30'),
                   dict(id='ntis-1283030', title='새 공고', url='https://www.ntis.go.kr/rndgate/eg/un/ra/view.do?roRndUid=1283030',
                        ministry='과학기술정보통신부', agency='', posted_date='2026-11-14', open_date='', close_date='', budget_won=None)]
        second, added = rc.build(first, changed, NOW)
        ids = [item['id'] for item in second['items']]
        self.assertEqual(added, 1)
        self.assertEqual(ids, ['ntis-1283030', 'ntis-1282959', 'ntis-1282000'])  # 공고일 최신순, 빠진 공고도 보관
        kept = next(item for item in second['items'] if item['id'] == 'ntis-1282959')
        self.assertEqual(kept['close_date'], '2026-11-30')
        self.assertEqual(kept['first_seen'], '2026-11-17')
        self.assertEqual(kept['status'], '접수중')

    def test_categories_follow_rss_fields(self):
        data, _ = rc.build({'categories': {'ministry': ['교육부'], 'type': ['본공고'], 'form': ['통합공고']}}, rc.parse_feed(SAMPLE), NOW)
        self.assertNotIn('type', data['categories'])  # RSS에 없는 공고유형·형태 필터는 만들지 않음
        self.assertNotIn('form', data['categories'])
        self.assertEqual(data['categories']['ministry'], ['과학기술정보통신부', '교육부', '농림축산식품부'])
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['source']['url'], 'https://www.ntis.go.kr/rndgate/eg/un/ra/mng.do')

    def test_keeps_at_most_max_items(self):
        rows = [dict(id=f'ntis-{n}', title=str(n), url='https://www.ntis.go.kr/', posted_date=f'2026-01-{n % 28 + 1:02d}')
                for n in range(rc.MAX_ITEMS + 10)]
        items, _ = rc.merge(rows, [], '2026-11-17', min_posted='')
        self.assertEqual(len(items), rc.MAX_ITEMS)

    def test_drops_announcements_posted_before_cutoff(self):
        old = dict(id='ntis-1', title='9월 공고', url='https://www.ntis.go.kr/', posted_date='2026-09-30')
        new = dict(id='ntis-2', title='10월 공고', url='https://www.ntis.go.kr/', posted_date='2026-10-01')
        undated = dict(id='ntis-3', title='공고일 없음', url='https://www.ntis.go.kr/', posted_date='')
        old_open = dict(old, id='ntis-5', close_date='2026-11-17')  # 이전 공고지만 오늘 마감 → 남김
        old_closed = dict(old, id='ntis-6', close_date='2026-11-16')
        items, added = rc.merge([old, old_closed], [dict(old, id='ntis-4'), new, undated, old_open], '2026-11-17', min_posted='2026-10-01')
        self.assertEqual(([item['id'] for item in items], added), (['ntis-2', 'ntis-5', 'ntis-3'], 3))
        # 다음 날 다시 합치면 마감된 이전 공고는 빠지고, 10월 이후 공고는 마감돼도 남음
        later, _ = rc.merge(items, [], '2026-11-18', min_posted='2026-10-01')
        self.assertEqual([item['id'] for item in later], ['ntis-2', 'ntis-3'])
        self.assertEqual(rc.MIN_POSTED_DATE, '2026-10-01')


class UpdateTest(unittest.TestCase):
    def test_writes_file_and_failure_keeps_existing(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'rnd-announcements.json'
            self.assertEqual(rc.update(path, raw=SAMPLE, now=NOW), (2, 2))
            saved = path.read_bytes()
            self.assertEqual(len(json.loads(saved)['items']), 2)
            for bad in (b'<html>error</html>', b'<rss><channel></channel></rss>', b'not xml'):
                with self.assertRaises(Exception):
                    rc.update(path, raw=bad, now=NOW)
                self.assertEqual(path.read_bytes(), saved)

    def test_backfill_by_day_skips_failures_and_dedups(self):
        from datetime import date
        empty = b'<?xml version="1.0"?><rss version="2.0"><channel><title>x</title></channel></rss>'
        asked = []

        def fake(day):
            asked.append(day.isoformat())
            if day == date(2026, 11, 12):
                raise OSError('timeout')
            return SAMPLE if day == date(2026, 11, 13) else empty

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'rnd-announcements.json'
            rc.update(path, raw=SAMPLE, now=NOW)  # 이미 있는 공고는 다시 세지 않음
            total, added, failed = rc.backfill(date(2026, 11, 10), date(2026, 11, 14), path, fake, delay=0, now=NOW, log=lambda _: None)
            self.assertEqual(asked, ['2026-11-10', '2026-11-11', '2026-11-12', '2026-11-13', '2026-11-14'])
            self.assertEqual((total, added, failed), (2, 0, ['2026-11-12']))
            self.assertEqual(len(json.loads(path.read_text(encoding='utf-8'))['items']), 2)

    def test_repository_data_file_shape(self):
        data = json.loads((rc.ROOT / 'rnd-announcements.json').read_text(encoding='utf-8'))
        self.assertIsInstance(data['items'], list)
        for key in ('status', 'ministry', 'scale', 'deadline'):
            self.assertTrue(data['categories'][key], key)
        ids = [item['id'] for item in data['items']]
        self.assertEqual(len(ids), len(set(ids)))
        for item in data['items']:
            self.assertTrue(item['url'].startswith('https://www.ntis.go.kr/'))
            if item.get('posted_date') and item['posted_date'] < rc.MIN_POSTED_DATE:
                self.assertTrue(item.get('close_date'), item['id'])  # 이전 공고는 마감일이 있는 미마감 공고만


if __name__ == '__main__':
    unittest.main()
