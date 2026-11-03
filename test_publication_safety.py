import io
import json
from copy import deepcopy
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

import rss_collector
import update_news
from publication_safety import publication_errors, PublicationBlocked


def article(article_id='a'):
    return dict(id=article_id,title='한양대학교 연구 성과 발표',url='https://example.com/'+article_id,
                original_url='https://example.com/original/'+article_id,date='2026-10-29T01:00:00+00:00',
                body='한양대학교 연구팀이 새로운 기술을 개발하고 연구 결과를 공개했다.',
                regions=['경기도','서울'],duplicate_ids=[article_id,'historical-'+article_id],duplicate_count=2)


def mock_run(root, xml=b'<rss><channel/></rss>'):
    (root/'rss_sources.json').write_text(json.dumps([dict(name='offline fixture',url='https://example.invalid/feed')]),encoding='utf-8')
    def response(request, **kwargs):
        assert request.full_url=='https://example.invalid/feed'
        return io.BytesIO(xml)
    with patch.object(rss_collector,'ROOT',root),patch.object(rss_collector,'CACHE',root/'.rss-cache.json'),patch.object(rss_collector,'urlopen',side_effect=response),patch.object(rss_collector,'resolve_newsroom_link',side_effect=lambda x:x),redirect_stdout(io.StringIO()):
        return update_news.update_news(root)


class PublicationPreservationTests(unittest.TestCase):
    def test_three_cold_runs_keep_public_and_raw_records(self):
        original=[article('a'),article('b')]
        payload=dict(news=original,status={})
        for _ in range(3):
            with TemporaryDirectory() as directory:
                root=Path(directory)
                self.assertFalse((root/'.rss-cache.json').exists())
                (root/'news.json').write_text(json.dumps(payload),encoding='utf-8')
                payload=mock_run(root)
                self.assertEqual(len(payload['news']),2)
                self.assertEqual(len(payload['raw_news']),2)
                for before,after in zip(original,payload['news']):
                    for key in ('id','title','url','original_url','date','body','regions'):
                        self.assertEqual(after[key],before[key])
                self.assertTrue(payload['region_change_reviews'])
                self.assertTrue(all(not r['automatic_change_applied'] for r in payload['region_change_reviews']))
                report=json.loads((root/'classification_diagnostics.json').read_bytes())
                self.assertEqual(report['region_change_reviews'],payload['region_change_reviews'])

    def test_new_article_gets_latest_rules(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);(root/'news.json').write_text(json.dumps(dict(news=[article()],status={})),encoding='utf-8')
            xml='<rss><channel><item><title>순천향대학교 새 연구 발표</title><link>https://example.invalid/new</link></item></channel></rss>'.encode()
            payload=mock_run(root,xml)
            self.assertEqual(len(payload['news']),2)
            self.assertEqual(len(payload['raw_news']),2)
            new=next(x for x in payload['news'] if x['id']!='a')
            self.assertEqual(new['regions'],['충남'])
            self.assertEqual(next(x for x in payload['news'] if x['id']=='a')['regions'],article()['regions'])

    def test_official_hospital_address_corrects_school_level_region(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);old=article();old.update(title='분당서울대병원 연구 발표',body='',regions=['서울'])
            (root/'news.json').write_text(json.dumps(dict(news=[old],status={})),encoding='utf-8')
            payload=mock_run(root)
            self.assertEqual(payload['news'][0]['regions'],['경기도'])
            review=payload['region_change_reviews'][0]
            self.assertEqual((review['proposed_regions'],review['decision'],review['automatic_change_applied']),(['경기도'],'verified_campus_correction',True))
            self.assertEqual({k:payload['news'][0][k] for k in ('id','title','url','original_url','date','body')},
                             {k:old[k] for k in ('id','title','url','original_url','date','body')})

    def test_region_written_in_article_is_not_corrected(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);old=article();old.update(title='서울 기관, 분당서울대병원과 연구 발표',body='',regions=['서울'])
            (root/'news.json').write_text(json.dumps(dict(news=[old],status={})),encoding='utf-8')
            payload=mock_run(root)
            self.assertEqual(payload['news'][0]['regions'],['서울'])
            self.assertFalse(any(r['automatic_change_applied'] for r in payload['region_change_reviews']))

    def test_guard_detects_region_raw_identity_and_alias_loss(self):
        old=article()
        cases=[('region',lambda row:row.update(regions=[])),('link',lambda row:row.pop('original_url')),
               ('date',lambda row:row.update(date='')),('body',lambda row:row.update(body='')),
               ('title',lambda row:row.update(title='changed')),('aliases',lambda row:row.update(duplicate_ids=[]))]
        for name,corrupt in cases:
            with self.subTest(case=name):
                new=deepcopy(old);corrupt(new)
                errors=publication_errors([old],[old],[new],[old])
                self.assertTrue(errors)
                self.assertIn('a',{id for error in errors for id in error['ids']})
        self.assertTrue(publication_errors([old],[old],[old],[]))
        self.assertTrue(publication_errors([old],[old],[],[old]))

    def test_guard_allows_only_policy_eviction_with_raw_preserved(self):
        a,b=article('a'),article('b')
        self.assertEqual(publication_errors([a],[a],[b],[a,b],{'b'}),[])
        self.assertTrue(publication_errors([a],[a],[b],[b],{'b'}))

    def test_writer_blocks_bad_collector_output_and_keeps_public_bytes(self):
        for corruption in ('regions','raw_loss','summary','nan'):
            with self.subTest(corruption=corruption),TemporaryDirectory() as directory:
                root=Path(directory);path=root/'news.json';old=article();path.write_text(json.dumps(dict(news=[old],status={})),encoding='utf-8');before=path.read_bytes()
                candidate=deepcopy(old);raw=[deepcopy(old)];status=dict(state='ready')
                if corruption=='regions':candidate['regions']=[]
                if corruption=='raw_loss':raw=[]
                if corruption=='summary':candidate['body']=''
                if corruption=='nan':status['bad']=float('nan')
                class Fake:
                    search_cursor=0;raw_news=raw;region_change_reviews=[];new_article_ids=set()
                    def refresh(self):pass
                    def snapshot(self):return [candidate],status
                with patch.object(update_news,'Collector',Fake),redirect_stdout(io.StringIO()):
                    with self.assertRaises(PublicationBlocked):update_news.update_news(root)
                self.assertEqual(path.read_bytes(),before)
                log=json.loads((root/'publication_safety_report.json').read_bytes())
                self.assertTrue(log['blocked'])
                self.assertTrue(log['violations'])

    def test_malformed_json_and_duplicate_ids_are_rejected(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);path=root/'news.json';path.write_text('{broken',encoding='utf-8');before=path.read_bytes()
            with redirect_stdout(io.StringIO()):
                with self.assertRaises(PublicationBlocked):update_news.update_news(root)
            self.assertEqual(path.read_bytes(),before)
        self.assertTrue(publication_errors([],[],[article(),article()],[article()]))
        bad=article();bad['pending_update']={'value':float('nan')}
        errors=publication_errors([],[],[bad],[bad])
        self.assertIn('a',{id for error in errors for id in error['ids']})


if __name__=='__main__':unittest.main()
