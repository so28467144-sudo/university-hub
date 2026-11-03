import copy
import unittest
from article_dedup import press_same_story, press_partitions, public_story_groups, duplicate_review_groups


def report(ident,title,source='A일보',date='2026-11-02T01:00:00+00:00',school='세종대학교',regions=('서울',),category='대학 소식',body=''):
    return dict(id=ident,title=title,source=source,date=date,school=school,school_names=[school],regions=list(regions),
                region=regions[0] if len(regions)==1 else '',category=category,body=body,url='https://example.org/'+ident)


class PressStoryTests(unittest.TestCase):
    def test_same_event_across_publishers_groups(self):
        a=report('a','세종대 지웅배 교수 초청 학정포럼 개최')
        b=report('b','세종대, 지웅배 교수 초청 학정포럼 성황리 개최',source='B신문',date='2026-11-02T05:00:00+00:00')
        self.assertTrue(press_same_story(a,b))
        groups=public_story_groups([a,b])
        self.assertEqual((groups[0]['version'],sorted(groups[0]['article_ids'])),(5,['a','b']))

    def test_uncertain_or_distinct_stories_stay_visible(self):
        base=report('a','세종대 지웅배 교수 초청 학정포럼 개최')
        cases={
            'other school':dict(school='경희대학교',title='경희대 지웅배 교수 초청 학정포럼 개최'),
            'other region':dict(regions=('경기도',)),
            'other category':dict(category='행사·특강'),
            'three days later':dict(date='2026-11-06T01:00:00+00:00'),
            'no shared event':dict(title='세종대 총장 연임 확정'),
        }
        for name,change in cases.items():
            with self.subTest(name=name):
                b=dict(report('b','세종대, 지웅배 교수 초청 학정포럼 성황리 개최',source='B신문'),**change)
                if 'school' in change:b['school_names']=[change['school']]
                self.assertFalse(press_same_story(base,b))

    def test_missing_date_or_unknown_school_or_region_stays_visible(self):
        a=report('a','세종대 지웅배 교수 초청 학정포럼 개최');b=report('b','세종대, 지웅배 교수 초청 학정포럼 성황리 개최')
        self.assertFalse(press_same_story(dict(a,date=''),b))
        self.assertFalse(press_same_story(dict(a,school_names=[]),dict(b,school_names=[])))
        self.assertFalse(press_same_story(dict(a,regions=[]),dict(b,regions=[])))

    def test_followup_and_new_facts_stay_separate(self):
        a=report('a','세종대 학정포럼 일정 발표')
        for title in ('세종대 학정포럼 일정 연기','세종대 학정포럼 취소','세종대 학정포럼 논란 해명','세종대 학정포럼 결과 발표'):
            with self.subTest(title=title):self.assertFalse(press_same_story(a,report('b',title)))

    def test_announcement_and_result_stay_separate(self):
        a=report('a','세종대 학정포럼 지웅배 교수 초청 다음달 개최')
        b=report('b','세종대 학정포럼 지웅배 교수 초청 성황리 마무리',source='B신문')
        self.assertFalse(press_same_story(a,b))

    def test_digest_title_and_long_gap_activity_stay_separate(self):
        a=report('a',"세종대 학정포럼 개최...산학협력 MOU 체결...AI 기술경영 과정 신설")
        b=report('b','세종대 학정포럼 개최',source='B신문')
        self.assertFalse(press_same_story(a,b))
        a=report('a','세종대 농심천심운동 전개 대학 협력 확대',date='2026-10-30T03:00:00+00:00')
        b=report('b','세종대 농심천심운동 실천 농촌 일손돕기',source='B신문',date='2026-11-01T05:00:00+00:00')
        self.assertFalse(press_same_story(a,b))

    def test_same_long_institution_name_with_different_projects_stays_separate(self):
        options=dict(school='수원대학교',regions=('경기도',))
        a=report('a',"수원대 운영 화성시 어린이/사회복지급식관리지원센터, '영양의 날' 맞이 식생활 캠페인 성료",**options)
        b=report('b','수원대 운영 화성시 어린이/사회복지급식관리지원센터, 사회복지급식소 이용자 대상 식생활 교구대여 사업 성료',source='B신문',**options)
        self.assertFalse(press_same_story(a,b))

    def test_conflicting_numbers_stay_separate(self):
        a=report('a','세종대 제14회 학정포럼 개최');b=report('b','세종대 제15회 학정포럼 개최')
        self.assertFalse(press_same_story(a,b))
        a=report('a','세종대 학정포럼 참가자 300명 모집');b=report('b','세종대 학정포럼 참가자 500명 모집')
        self.assertFalse(press_same_story(a,b))

    def test_different_angle_with_much_other_title_information_stays_separate(self):
        options=dict(school='인하대학교',regions=('인천',))
        a=report('a','남자프로배구 대한항공, 이승일·송정민·홍준범 지명… ‘전관왕 에이스’ 윤경(인하대)은 전체 1순위로 OK저축은행행',**options)
        b=report('b','인하대 배구부 4명 프로 진출…윤경 전체 1순위로 OK저축은행행',**options)
        self.assertFalse(press_same_story(a,b))

    def test_editorial_and_digest_stay_separate(self):
        a=report('a','세종대 학정포럼 개최 칼럼');b=report('b','세종대 학정포럼 개최 칼럼',source='B신문')
        self.assertFalse(press_same_story(a,b))

    def test_body_disagreement_blocks_grouping(self):
        a=report('a','세종대 지웅배 교수 초청 학정포럼 개최',body='천문학 강연을 열어 학생들과 우주를 이야기했다. '*6)
        b=report('b','세종대, 지웅배 교수 초청 학정포럼 성황리 개최',body='장학금 전달식과 동문회 총회가 함께 진행됐다는 소식이다. '*6)
        self.assertFalse(press_same_story(a,b))

    def test_admission_without_explicit_year_stays_separate(self):
        a=report('a','세종대 전기 대학원 신입생 모집',category='입시·모집')
        b=report('b','세종대 2027학년도 대학원 신입생 모집',category='입시·모집')
        self.assertFalse(press_same_story(a,b))

    def test_groups_are_cliques_not_chains(self):
        rows=[report('a','세종대 학정포럼 지웅배 교수 강연'),report('b','세종대 학정포럼 지웅배 교수 강연 개최',source='B'),
              report('c','세종대 학정포럼 취소',source='C')]
        parts=press_partitions(rows)
        for part in parts:
            for x in part:
                for y in part:
                    if x is not y:self.assertTrue(press_same_story(x,y))

    def test_rows_are_not_mutated_or_removed(self):
        rows=[report('a','세종대 지웅배 교수 초청 학정포럼 개최'),report('b','세종대, 지웅배 교수 초청 학정포럼 성황리 개최',source='B')]
        before=copy.deepcopy(rows)
        public_story_groups(rows);duplicate_review_groups(rows)
        self.assertEqual(rows,before)

    def test_grouped_story_is_not_also_review_candidate(self):
        rows=[report('a','세종대 지웅배 교수 초청 학정포럼 개최'),report('b','세종대, 지웅배 교수 초청 학정포럼 성황리 개최',source='B')]
        self.assertEqual(duplicate_review_groups(rows),[])


if __name__=='__main__':
    unittest.main()
