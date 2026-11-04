import copy
import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from article_dedup import confirmed_same_story, confirmed_deduplicate, public_story_groups
from test_publication_safety import mock_run


def record(ident='a'):
    return dict(id=ident,title='세종대학교 과학 연구 성과 발표',
                body='세종대학교 연구진은 새로운 과학 기술의 연구 결과와 검증 방법을 발표했다. '*8,
                school='세종대학교',regions=['서울'],region='서울',category='연구·성과',
                source='공식 뉴스룸',date='2026-11-02T01:00:00+00:00',
                url='https://example.org/articles/123',original_url='https://example.org/articles/123')


class ConservativePublicDuplicates(unittest.TestCase):
    def test_identical_complete_records_can_merge(self):
        self.assertTrue(confirmed_same_story(record(),record('b')))
        self.assertEqual(len(public_story_groups([record(),record('b')])),1)

    def test_distinct_user_information_never_hidden(self):
        for key,value in dict(title='세종대 과학 연구 결과 공개',body='다른 요약 '*100,
                              source='다른 언론사',regions=['경기도'],date='2026-11-02T02:00:00+00:00',
                              url='https://example.org/articles/124',original_url='',
                              category='대학 소식',school_aliases=['세종대']).items():
            with self.subTest(key=key):
                b=record('b');b[key]=value
                self.assertFalse(confirmed_same_story(record(),b))
                self.assertEqual(len(confirmed_deduplicate([record(),b])),2)

    def test_editorial_followup_digest_excluded_even_if_identical(self):
        for label in ['칼럼','창간 축사','인터뷰','후속 보도','논평','교육소식]',
                      '대학 브리핑','아주대 사직','경찰 압수수색','소식 모음']:
            with self.subTest(label=label):
                a=record();a['title']=label+' '+a['title'];b=dict(a,id='b')
                # 비슷한 보도로는 묶지 않고, 같은 매체가 같은 기사를 다시 수집한 경우만 같은 제목 묶음이 됩니다.
                self.assertEqual([g for g in public_story_groups([a,b]) if g['version']!=6],[])
                self.assertEqual(public_story_groups([a,dict(b,source='다른 언론사')]),[])

    def test_notice_without_real_body_is_candidate_only(self):
        a=record();a['body']='구글 뉴스에서 수집한 기사입니다. 기사 내용을 확인하려면 기사 보기 버튼을 눌러 주세요.'
        # 안내문뿐인 기사는 비슷한 보도로 묶지 않습니다. 제목·매체가 같은 재수집본만 같은 제목 묶음이 됩니다.
        self.assertEqual([g for g in public_story_groups([a,dict(a,id='b')]) if g['version']!=6],[])
        self.assertEqual(public_story_groups([a,dict(a,id='b',title='세종대학교 과학 연구 성과 공개')]),[])

    def test_representative_preserves_input(self):
        rows=[record(),record('b')];before=copy.deepcopy(rows)
        out=confirmed_deduplicate(rows)
        self.assertEqual(rows,before)
        self.assertEqual(set(out[0]['duplicate_ids']),{'a','b'})

    def test_new_rss_uncertain_admissions_both_remain_public(self):
        xml='''<rss><channel>
        <item><title>건양대, 전기 대학원 신입생 413명 모집</title><link>https://example.invalid/a</link><pubDate>Mon, 02 Nov 2026 01:00:00 GMT</pubDate></item>
        <item><title>건양대, 2027학년도 대학원 신입생 모집</title><link>https://example.invalid/b</link><pubDate>Mon, 02 Nov 2026 01:00:00 GMT</pubDate></item>
        </channel></rss>'''.encode()
        with TemporaryDirectory() as d:
            root=Path(d)
            (root/'news.json').write_text(json.dumps(dict(news=[],status={})),encoding='utf-8')
            out=mock_run(root,xml)
            self.assertEqual(len(out['news']),2)
            self.assertEqual(len(out['raw_news']),2)
            self.assertEqual(out['status']['public_story_groups'],[])
            self.assertTrue(out['status']['duplicate_review_candidates'])


if __name__=='__main__':unittest.main()
