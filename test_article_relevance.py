import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from article_relevance import classify_relevance, hospital_subject, listed
from test_publication_safety import mock_run


def relevance(title):
    return classify_relevance(dict(title=title))[0]


class HospitalRelevanceTests(unittest.TestCase):
    def test_hospital_operations_are_excluded(self):
        for title in ('건양대병원, 다빈치 SP 1천례…산부인과 로봇수술 2천례','인하대병원, 의료질평가 7년 연속 최상위 등급',
                      '충남대학교병원, 세계 뇌졸중의 날 캠페인 열어','제주대병원, 개원 25주년 기념식 개최',
                      '가톨릭대 성빈센트병원, 결핵 적정성 평가 1등급','순천향대서울병원, 혈액종양 집중치료 병동 오픈'):
            with self.subTest(title=title):
                self.assertEqual(relevance(title),'hospital_excluded')

    def test_research_and_education_stay(self):
        for title in ('분당서울대병원, 내장지방 악화 원인 규명','강원대병원 최상지 교수, NEJM 논평 게재',
                      '단국대병원 우상범 전공의, 대한재활의학회 우수연제상 수상','서울대병원 서지연 교수팀, 선종 크기별 위험 분석',
                      '세종충남대학교병원 최규태 교수, 진단검사 자동화 공모전 최우수상','고려대의료원, 전공의 수련교육 혁신'):
            with self.subTest(title=title):
                self.assertNotEqual(relevance(title),'hospital_excluded')

    def test_reported_borderline_cases(self):
        self.assertEqual(relevance('강동경희대병원, 호흡기질환 평가 결과 공개…결핵 99.8점'),'hospital_excluded')
        self.assertEqual(relevance("화순전남대병원, 첨단 감마나이프 '에스프릿' 도입"),'hospital_excluded')
        self.assertNotEqual(relevance("한양대구리병원 황선진 교수, BRIC '한국을 빛내는 사람들' 선정"),'hospital_excluded')
        self.assertNotEqual(relevance("건국대병원 이종호 전공의 '수혈 전 혈액 품질 평가 지표' 우수구연상 수상"),'hospital_excluded')
        self.assertIsNone(__import__('re').search(__import__('article_relevance').ACADEMIC,'전북교육청 협약'))

    def test_uncertain_hospital_articles_are_kept_for_review(self):
        for title in ('강동경희대병원, 우주의학센터 개소…융합연구 본격','원광대병원, 교당에 교화지원금 전달','아주대병원 압수수색 논란'):
            with self.subTest(title=title):
                self.assertEqual(relevance(title),'review')

    def test_university_article_is_not_judged_by_a_hospital_word(self):
        self.assertFalse(hospital_subject('경희대, 강동경희대병원과 공동 연구 협약'))
        self.assertFalse(hospital_subject('세종대 학생 봉사단, 지역 병원 방문'))
        self.assertFalse(hospital_subject('제주대 부설동물병원 증축…전문 진료 기반 확충'))
        self.assertEqual(relevance('연세대 연구팀 기술 개발'),'university')

    def test_listed_keeps_review_and_drops_only_exclusions(self):
        rows=[dict(id='a',relevance='university'),dict(id='b',relevance='review'),dict(id='c',relevance='hospital_excluded')]
        self.assertEqual([r['id'] for r in listed(rows)],['a','b'])

    def test_pipeline_records_reason_and_keeps_rows(self):
        xml='''<rss><channel>
        <item><title>인하대병원, 의료질평가 7년 연속 최상위 등급</title><link>https://example.invalid/h</link><pubDate>Mon, 02 Nov 2026 01:00:00 GMT</pubDate></item>
        <item><title>인하대 연구팀, 배터리 신소재 개발</title><link>https://example.invalid/u</link><pubDate>Mon, 02 Nov 2026 02:00:00 GMT</pubDate></item>
        </channel></rss>'''.encode()
        with TemporaryDirectory() as d:
            root=Path(d)
            (root/'news.json').write_text(json.dumps(dict(news=[],status={})),encoding='utf-8')
            out=mock_run(root,xml)
            self.assertEqual([r['url'] for r in out['news']],['https://example.invalid/u'])
            raw={r['url']:r for r in out['raw_news']}
            self.assertEqual(len(raw),2)
            hospital=raw['https://example.invalid/h']
            self.assertEqual(hospital['relevance'],'hospital_excluded')
            self.assertTrue(hospital['relevance_reason'])
            self.assertEqual(out['status']['relevance_counts'],dict(university=1,review=0,hospital_excluded=1))
            again=mock_run(root,xml)
            self.assertEqual(again['status']['relevance_counts']['hospital_excluded'],1)
            self.assertEqual([r['url'] for r in again['news']],['https://example.invalid/u'])


class PublicLimitTests(unittest.TestCase):
    def article(self,ident,title,date):
        return dict(id=ident,title=title,url='https://example.invalid/'+ident,original_url='',date=date,body='',
                    regions=[],duplicate_ids=[ident],duplicate_count=1)

    def test_excluded_slots_are_refilled_from_raw(self):
        from rss_collector import publish_university_articles
        news=[self.article('h','인하대병원, 의료질평가 최상위 등급','2026-11-02T03:00:00+00:00'),
              self.article('u','인하대 연구팀, 신소재 개발','2026-11-02T02:00:00+00:00')]
        pool=news+[self.article('old','성균관대 학생 창업 성과','2026-10-01T00:00:00+00:00'),
                   self.article('oldh','충남대병원, 뇌졸중 캠페인','2026-10-02T00:00:00+00:00')]
        raw={r['id']:dict(r) for r in pool}
        shown,excluded=publish_university_articles([dict(r) for r in news],pool,raw,limit=2)
        self.assertEqual([r['id'] for r in shown],['u','old'])
        self.assertEqual(excluded,{'h','oldh'})
        self.assertEqual((raw['h']['relevance'],bool(raw['h']['relevance_reason'])),('hospital_excluded',True))
        self.assertNotIn('relevance',raw['old'])

    def test_previous_public_row_returning_after_eviction_keeps_its_published_regions(self):
        from rss_collector import publish_university_articles
        old=dict(self.article('old','서울대 연구팀 기술 개발','2026-10-01T00:00:00+00:00'),regions=['서울'],school='서울대학교')
        new=self.article('new','인하대 연구팀 신소재 개발','2026-11-02T02:00:00+00:00')
        hospital=self.article('h','인하대병원, 의료질평가 최상위 등급','2026-11-02T03:00:00+00:00')
        # 새 기사가 들어와 old가 한도 밖으로 밀린 뒤, 병원 기사 제외로 생긴 자리에 다시 들어오는 경우입니다.
        pool=[hospital,new,dict(old,regions=[],title='‘인간중심 AI’는 너무 모호하다')]
        shown,excluded=publish_university_articles([dict(hospital),dict(new)],pool,{},limit=2,previous_public={'old':old})
        returned=next(r for r in shown if r['id']=='old')
        self.assertEqual((returned['regions'],returned['title']),(['서울'],'서울대 연구팀 기술 개발'))
        self.assertEqual(excluded,{'h'})

    def test_real_collection_with_new_articles_and_exclusions_is_not_blocked(self):
        xml='''<rss><channel>
        <item><title>인하대 연구팀, 배터리 신소재 개발</title><link>https://example.invalid/n1</link><pubDate>Mon, 02 Nov 2026 02:00:00 GMT</pubDate></item>
        </channel></rss>'''.encode()
        rows=[dict(self.article('h','인하대병원, 의료질평가 최상위 등급','2026-11-01T03:00:00+00:00'),regions=['인천'],school='인하대학교'),
              dict(self.article('o','‘인간중심 AI’는 너무 모호하다…서울대 교수','2026-10-01T00:00:00+00:00'),regions=['서울'],school='서울대학교')]
        with TemporaryDirectory() as d:
            root=Path(d)
            (root/'news.json').write_text(json.dumps(dict(news=rows,status={})),encoding='utf-8')
            import rss_collector
            original=rss_collector.MAX_ARTICLES
            try:
                rss_collector.MAX_ARTICLES=2
                out=mock_run(root,xml)
            finally:
                rss_collector.MAX_ARTICLES=original
            by={r['id']:r for r in out['news']}
            self.assertEqual(by['o']['regions'],['서울'])
            self.assertNotIn('h',by)

    def test_review_articles_are_not_removed(self):
        from rss_collector import publish_university_articles
        news=[self.article('r','아주대병원 압수수색 논란','2026-11-02T03:00:00+00:00')]
        shown,excluded=publish_university_articles(news,news,{},limit=5)
        self.assertEqual(([r['relevance'] for r in shown],excluded),(['review'],set()))

    def test_guard_accepts_only_recorded_exclusions(self):
        from publication_safety import publication_errors
        old=[self.article('h','x','2026-11-02T03:00:00+00:00'),self.article('u','y','2026-11-02T02:00:00+00:00')]
        raw=[dict(r) for r in old]
        refill=self.article('old','z','2026-10-01T00:00:00+00:00');raw.append(dict(refill))
        reasons={r.pop('reason') for r in publication_errors(old,raw,[old[1],refill],[dict(r) for r in raw],set(),{'h'})}
        self.assertIn('excluded_record_without_reason',reasons)
        raw[0].update(relevance='hospital_excluded',relevance_reason='부속 병원 운영 소식')
        self.assertEqual(publication_errors(old,raw,[old[1],refill],raw,set(),{'h'}),[])
        self.assertTrue(publication_errors(old,raw,[old[1]],raw,set(),set()))
        self.assertTrue(publication_errors(old,raw,[old[1],refill],[r for r in raw if r['id']!='h'],set(),{'h'}))


if __name__=='__main__':
    unittest.main()
