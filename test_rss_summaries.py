import hashlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest
import xml.etree.ElementTree as ET

import rss_collector
from rss_collector import parse_feed, deduplicate_preserving_links
from rss_summaries import GOOGLE_NOTICE, select_summary, preserve_summary, assess_summary

TITLE = '한양대학교 연구 소식'
BODY = '한양대학교 ERICA캠퍼스 연구팀이 새로운 기술을 개발하고 연구 성과를 발표했다.'


def item(fields, google=False):
    link = 'https://news.google.com/rss/articles/synthetic-only' if google else 'https://example.com/article'
    xml = ('<rss xmlns:content="http://purl.org/rss/1.0/modules/content/" '
           'xmlns:media="http://search.yahoo.com/mrss/" xmlns:atom="http://www.w3.org/2005/Atom" '
           'xmlns:unknown="https://example.com/unknown"><channel><item><title>'+TITLE+'</title><link>'+link+
           '</link><pubDate>Thu, 29 Oct 2026 01:00:00 GMT</pubDate><source>테스트신문</source>'+fields+'</item></channel></rss>')
    return parse_feed(xml.encode(), '테스트 RSS')[0]


class SummarySelectionTests(unittest.TestCase):
    def test_empty_description_and_useful_content(self):
        row = item('<description/><content:encoded>'+BODY+'</content:encoded>')
        self.assertEqual(row['body'], BODY)
        self.assertEqual(row['summary_source'], 'rss_content_encoded')

    def test_useful_description_beats_long_notice_content(self):
        row = item('<description>'+BODY+'</description><content:encoded>ⓒ RSS 피드는 개인 이용만 허용. 무단 재배포 금지. '+('서비스 안내문입니다. '*100)+'</content:encoded>')
        self.assertEqual(row['body'], BODY)
        self.assertEqual(row['summary_kind'], 'article_summary')
        self.assertEqual(row['summary_source'], 'rss_description')

    def test_title_and_publisher_echo_are_not_summary(self):
        row = item('<description>'+TITLE+' - 테스트신문</description>', True)
        self.assertEqual(row['summary_kind'], 'notice')
        self.assertEqual(row['body'], GOOGLE_NOTICE)

    def test_google_notice_only(self):
        row = item('<description>'+GOOGLE_NOTICE+'</description>', True)
        self.assertEqual(row['summary_kind'], 'notice')

    def test_google_useful_synthetic_summary_is_kept(self):
        row = item('<description>'+BODY+'</description>', True)
        self.assertEqual(row['body'], BODY)
        self.assertEqual(row['summary_kind'], 'article_summary')
        self.assertEqual(row['regions'], ['경기도'])

    def test_namespace_media_and_external_atom_content_excluded(self):
        row = item('<media:content>'+BODY+' 오류 미디어</media:content><unknown:content>'+BODY+'</unknown:content><atom:content src="https://example.com/external"/>'
                   '<description>'+BODY+'</description>')
        self.assertEqual(row['summary_source'], 'rss_description')
        row = item('<atom:content type="html">&lt;p&gt;'+BODY+'&lt;/p&gt;</atom:content>')
        self.assertEqual(row['summary_source'], 'atom_content')
        self.assertEqual(row['body'], BODY)

    def test_xhtml_and_scripts(self):
        row = item('<atom:content type="xhtml"><div xmlns="http://www.w3.org/1999/xhtml"><p>'+BODY+'</p><script>광고 내용</script></div></atom:content>')
        self.assertEqual(row['body'], BODY)

    def test_xml_field_order_does_not_change_selection(self):
        a='<description>'+BODY+'</description>'; b='<content:encoded>기사 내용을 확인하려면 원문을 보세요.</content:encoded>'
        self.assertEqual(item(a+b)['body'], item(b+a)['body'])

    def test_announcement_and_other_kinds(self):
        kind = assess_summary('대학 홈페이지 바로가기 > 초빙분야 - 간호학과 / 정년트랙 / 정신간호학. 홈페이지를 참고하시기 바랍니다.')[0]
        self.assertEqual(kind, 'announcement_excerpt')
        self.assertEqual(assess_summary('[인터뷰_홍길동 교수]')[0], 'other')


class SummaryPreservationTests(unittest.TestCase):
    def test_useful_previous_survives_notice_and_empty(self):
        previous = dict(id='a',title=TITLE,body=BODY)
        for body in (GOOGLE_NOTICE, ''):
            incoming = dict(id='a',title=TITLE,body=body,url='https://example.com/new',date='2026-10-29')
            merged = preserve_summary(previous, incoming)
            self.assertEqual(merged['body'], BODY)
            self.assertEqual(merged['summary_source'], 'legacy_body')
            self.assertEqual(merged['url'], incoming['url'])
            self.assertEqual(previous['body'], BODY)

    def test_notice_replaced_by_useful_and_conflicts_use_quality_source(self):
        old=dict(id='a',title=TITLE,body=GOOGLE_NOTICE)
        new=dict(id='a',title=TITLE,body=BODY,summary_source='rss_description')
        self.assertEqual(preserve_summary(old,new)['body'],BODY)
        old=dict(new)
        weaker=dict(new,body=BODY+' '+GOOGLE_NOTICE,summary_source='rss_content_encoded')
        self.assertEqual(preserve_summary(old,weaker)['body'],BODY)
        with self.assertRaises(ValueError):preserve_summary(old,dict(new,id='other'))

    def test_duplicate_links_preserved_by_existing_dedup(self):
        row=dict(id='a',title=TITLE,body=BODY,date='2026-10-29',url='https://example.com',duplicate_ids=['a','historical'])
        result=deduplicate_preserving_links([row])
        self.assertEqual(result[0]['duplicate_ids'],['a','historical'])

    def test_recollection_in_isolated_collector_preserves_identity(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);cache=root/'cache.json'
            link='https://news.google.com/rss/articles/synthetic-only'
            article_id=hashlib.sha256(link.encode()).hexdigest()[:24]
            old=dict(id=article_id,title=TITLE,body=BODY,url=link,original_url='https://example.com/original',
                     source='테스트신문',date='2026-10-29T01:00:00+00:00',duplicate_ids=[article_id,'historical'],duplicate_count=2,first_seen='keep')
            cache.write_text(json.dumps(dict(news=[old],raw_news=[old])),encoding='utf-8')
            (root/'rss_sources.json').write_text(json.dumps([dict(name='fixture',url='https://example.com/feed')]),encoding='utf-8')
            raw=('<rss><channel><item><title>'+TITLE+'</title><link>'+link+'</link><description>'+TITLE+'</description></item></channel></rss>').encode()
            with patch.object(rss_collector,'ROOT',root),patch.object(rss_collector,'CACHE',cache),patch.object(rss_collector,'urlopen',side_effect=lambda *a,**k:io.BytesIO(raw)):
                collector=rss_collector.Collector()
                for _ in range(2):
                    collector.refresh()
                    self.assertEqual(len(collector.news),1)
                    row=collector.news[0]
                    for key in ('id','url','original_url','date','body','first_seen'):
                        self.assertEqual(row[key],old[key],key)
                    self.assertEqual(set(row['duplicate_ids']),set(old['duplicate_ids']))
                    self.assertEqual(row['regions'],['경기도'])


if __name__=='__main__':unittest.main()
