import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import rss_collector
from rss_collector import parse_feed
from classification_monitor import build_report,inspect_article

def feed(title):
    from xml.sax.saxutils import escape
    return ('<rss><channel><item><title>'+escape(title)+'</title><link>https://example.com/article/1</link>'
            '<pubDate>Thu, 29 Oct 2026 06:00:00 GMT</pubDate></item></channel></rss>').encode()

class MonitorTests(unittest.TestCase):
    def test_incoming_feed_uses_new_classification_rules(self):
        cases=[('가천대 길병원, 나눔 행사','가천대학교','인천','행사·특강'),
               ('상명대-美 리하이대, 국제 학술세미나 개최','상명대학교','해외','행사·특강'),
               ('화순전남대병원 오페라 공연 개최','전남대학교','전남','행사·특강'),
               ('세종사이버대 콜로키움 성료','세종사이버대학교','서울','행사·특강')]
        for title,school,region,category in cases:
            item=parse_feed(feed(title),'임의의 신규 RSS')[0]
            self.assertIn(school,item['school_names'])
            self.assertIn(region,item['regions'])
            self.assertEqual(item['category'],category)
            self.assertEqual(inspect_article(item),( [], [] ))

    def test_expected_unknown_and_real_integrity_error_are_separate(self):
        item=parse_feed(feed('한국폴리텍대학 장학금 기탁'),'테스트')[0]
        self.assertEqual(build_report([item])['error_count'],0)
        broken=dict(item,regions=['서울'])
        self.assertIn('region_evidence_mismatch',inspect_article(broken)[0])
        unseen=parse_feed(feed('새봄대학교 연구 발표'),'테스트')[0]
        self.assertIn('unrecognized_school_name',inspect_article(unseen)[1])
        general=parse_feed(feed('교육부 선도대학 지원 발표'),'테스트')[0]
        self.assertNotIn('unrecognized_school_name',inspect_article(general)[1])

    def test_collector_checks_every_refresh_and_preserves_first_seen(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'rss_sources.json').write_text(json.dumps([dict(name='테스트',url='https://example.com/rss')]),encoding='utf-8')
            raw=feed('한밭대 연구성과 발표')
            with patch.object(rss_collector,'ROOT',root),patch.object(rss_collector,'CACHE',root/'cache.json'),patch.object(rss_collector,'urlopen',side_effect=lambda *a,**k:io.BytesIO(raw)):
                collector=rss_collector.Collector()
                collector.refresh()
                first=collector.raw_news[0]['first_seen']
                self.assertEqual(collector.status['classification_check']['new_count'],1)
                collector.refresh()
                self.assertEqual(collector.status['classification_check']['new_count'],0)
                self.assertEqual(collector.status['classification_check']['updated_count'],1)
                self.assertEqual(collector.raw_news[0]['first_seen'],first)
                report=json.loads((root/'classification_monitor_report.json').read_text(encoding='utf-8'))
                self.assertEqual(report['error_count'],0)
