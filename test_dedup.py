import unittest
from itertools import permutations
from article_dedup import deduplicate


def article(id,title,body='',school='세종대학교',date='2026-10-29T02:00:00+00:00'):
    return dict(id=id,title=title,body=body,school=school,date=date,url='https://example.com/'+id,via_google=True)


class DedupTests(unittest.TestCase):
    def test_shared_homepage_or_listing_url_does_not_merge_articles(self):
        for url in ('https://example.com/','https://example.com/news','https://example.com/index.do'):
            first=article('1','세종대 반도체 연구성과 발표')
            second=article('2','세종대 신입생 입학식 개최')
            first['url']=second['url']=url
            self.assertEqual(len(deduplicate([first,second])),2)

    def test_generic_news_title_is_not_enough_to_merge(self):
        rows=[article('1','월영소식'),article('2','월영소식')]
        self.assertEqual(len(deduplicate(rows)),2)

    def test_same_visit_different_activities_remain_separate(self):
        rows=[article('1','충남도립대 독일 하노버 소녀합창단과 국제교류 합창공연 개최'),
              article('2','충남도립대 독일 하노버 소녀합창단과 김밥 체험 국제교류 진행')]
        self.assertEqual(len(deduplicate(rows)),2)

    def test_same_local_event_with_different_headlines(self):
        titles=['숭실대입구역 일대, 창업·문화 중심 걷고 싶은 대학가로',
                "숭실대입구역 일대 '청년 특화거리'로…창업·주거·문화시설 조성",
                "숭실대입구역 일대 '청년·창업 거점'으로…지구단위계획 수정가결",
                '숭실대입구역 일대, 청년 창업·문화거리로 조성',
                '숭실대입구역 일대 청년·문화특화 거리로…임대주택도 조성']
        items=[article(str(i),title,school='대학명 미확인') for i,title in enumerate(titles)]
        result=deduplicate(items)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['duplicate_count'],5)
        for permutation in permutations(items):
            self.assertEqual(len(deduplicate(permutation)),1)

    def test_real_matching_summary_with_different_headlines(self):
        body='세종대학교는 학생의 진로 탐색을 돕는 특별 교육을 진행했다. '+ '프로그램 일정과 참가 대상, 교육 내용을 구체적으로 안내하고 현장 실습 및 상담을 함께 제공했다. '*4
        rows=[article('1','세종대 학생 진로 체험 소식',body=body),
              article('2','새로운 교육 모델로 진로 역량 높인다',body=body)]
        self.assertEqual(len(deduplicate(rows)),1)

    def test_other_locations_and_unrelated_events_remain_separate(self):
        titles=['중앙시장거리 청년 창업·문화 공간 조성',
                '중앙시장거리, 문화·창업 시설과 청년 주택 확충',
                '중앙시장거리 교통사고 운전자 검거',
                '남부시장거리 청년 창업·문화 공간 조성']
        rows=[article(str(i),title,school='대학명 미확인') for i,title in enumerate(titles)]
        result=deduplicate(rows)
        self.assertEqual(len(result),3)
        self.assertTrue(any(set(n['duplicate_ids'])=={'0','1'} for n in result))

    def test_same_university_different_research_stays_separate(self):
        titles=['세종대 인공지능 연구로 암 진단 정확도 향상',
                '세종대 인공지능 연구로 교통 혼잡 예측 정확도 향상']
        self.assertEqual(len(deduplicate([article(str(i),t) for i,t in enumerate(titles)])),2)

    def test_identical_titles_group_before_fuzzy_matches(self):
        items=[article('1','업무 보고 하는 유재수 충북대 총장 직무대리',school='충북대학교'),
               article('2','[국감]유재수 충북대학교 총장 직무대리',school='충북대학교'),
               article('3','업무보고하는 유재수 충북대총장 직무대리',school='충북대학교')]
        groups=deduplicate(items)
        self.assertTrue(any({'1','3'}.issubset(n['duplicate_ids']) for n in groups))

    def test_short_title_punctuation_does_not_escape_dedup(self):
        self.assertEqual(len(deduplicate([article('1','세종대 연구성과'),article('2','세종대, 연구성과')])),1)

    def test_formal_university_name_and_short_name_are_equivalent(self):
        first=article('1','숭실대 인공지능 연구센터 개소',school='숭실대학교')
        second=article('2','숭실대학교 인공지능 연구센터 개소',school='숭실대학교')
        self.assertEqual(len(deduplicate([first,second])),1)

    def test_distinct_campuses_and_results_are_not_combined(self):
        first=article('1',"한양대 서울캠퍼스 '구글 워크스페이스 구축과정' 운영",school='한양대학교')
        second=article('2',"한양대 ERICA캠퍼스 '구글 워크스페이스 구축과정' 운영",school='한양대학교')
        first['universities']=[dict(name='한양대학교',campus_status='matched',campus_names=['서울캠퍼스'])]
        second['universities']=[dict(name='한양대학교',campus_status='matched',campus_names=['ERICA캠퍼스'])]
        self.assertEqual(len(deduplicate([first,second])),2)
        before=article('3',"세종대 '구글 워크스페이스 구축과정' 운영")
        after=article('4',before['title']+' 결과 발표')
        self.assertEqual(len(deduplicate([before,after])),2)

    def test_reported_three_titles_keep_most_detailed(self):
        items=[article('1','“디지털 협업의 핵심을 잡다”… 세종대 대학일자리플러스센터, ‘구글 워크스페이스 구축과정’ 전격 운영'),
               article('2','세종대 대학일자리플러스센터, ‘구글 워크스페이스 구축과정’ 운영'),
               article('3',"세종대 대학일자리플러스센터 '구글 워크스페이스 구축과정' 운영.. '졸업생/지역 청년 디지털 협업 역량 강화'")]
        result=deduplicate(items)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['id'],'3')
        self.assertEqual(result[0]['duplicate_ids'],['1','2','3'])

    def test_real_summary_wins_over_longer_title(self):
        first=article('1','세종대 구글 워크스페이스 구축과정 운영',body='구글 뉴스에서 수집한 기사입니다. 안내 문구')
        second=article('2','세종대 구글 워크스페이스 구축과정 운영',body='교육은 11월 1일부터 3일까지 30명을 대상으로 진행한다. 신청 방법과 교육 일정, 문의처를 안내했다.')
        self.assertEqual(deduplicate([first,second])[0]['id'],'2')

    def test_different_schools_courses_dates_and_followups_preserved(self):
        base=article('1',"세종대 '구글 워크스페이스 구축과정' 운영")
        other_school=article('2',base['title'].replace('세종대','숭실대'),school='숭실대학교')
        other_course=article('3',base['title'].replace('구축과정','활용과정'))
        later=article('4',base['title'],date='2026-11-05T02:00:00+00:00')
        canceled=article('5',base['title']+' 취소')
        self.assertEqual(len(deduplicate([base,other_school,other_course,later,canceled])),5)

    def test_exact_link_and_tracking_duplicate(self):
        first=article('1','세종대 연구 성과')
        second=article('2','수정된 기사 제목')
        second['url']=first['url']+'?utm_source=test'
        self.assertEqual(len(deduplicate([first,second])),1)


if __name__=='__main__':unittest.main()
