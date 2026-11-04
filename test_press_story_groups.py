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


class IdenticalTitleTests(unittest.TestCase):
    def test_same_title_from_different_links_groups_even_if_classification_differs(self):
        a=report('a','세종대 학정포럼 지웅배 교수 초청 강연 개최',source='교수신문')
        b=dict(report('b','세종대 학정포럼 지웅배 교수 초청 강연 개최 - 머니투데이',source='교수신문',date='2026-11-02T05:00:00+00:00'),
               regions=['경기도','서울'],category='행사·특강')
        groups=[g for g in public_story_groups([a,b]) if g['version']==6]
        self.assertEqual([sorted(g['article_ids']) for g in groups],[['a','b']])

    def test_punctuation_quotes_and_suffix_are_normalized(self):
        from article_dedup import title_identity
        self.assertEqual(title_identity(report('a',"세종대, ‘2026 학정포럼’ 개최 > 뉴스")),title_identity(report('b','세종대 2026 학정포럼 개최')))
        self.assertTrue(title_identity(report('c','부산광역시의회「2026년 대학생 모의의회 경연대회」개최',school='대학명 미확인')))

    def test_same_title_on_distant_dates_or_generic_title_stays_separate(self):
        a=report('a','세종대 학정포럼 지웅배 교수 초청 강연 개최')
        b=report('b','세종대 학정포럼 지웅배 교수 초청 강연 개최',date='2026-11-08T01:00:00+00:00')
        self.assertEqual([g for g in public_story_groups([a,b]) if g['version']==6],[])
        c=report('c','[인사] 세종대학교');d=report('d','[인사] 세종대학교',date='2026-11-02T09:00:00+00:00')
        self.assertEqual(public_story_groups([c,d]),[])
        e=report('e','월영소식',school='경남대학교');f=report('f','월영소식',school='경남대학교',date='2026-11-02T02:00:00+00:00')
        self.assertEqual(public_story_groups([e,f]),[])

    def test_same_title_with_contradicting_summaries_stays_separate(self):
        a=report('a','세종대 학정포럼 지웅배 교수 초청 강연 개최',body='천문학 강연을 열어 학생들과 우주를 이야기했다. '*6)
        b=report('b','세종대 학정포럼 지웅배 교수 초청 강연 개최',body='장학금 전달식과 동문회 총회 등 전혀 다른 일정이 이어졌다는 소식이다. '*6)
        self.assertEqual([g for g in public_story_groups([a,b]) if g['version']==6],[])


class EventEntityTests(unittest.TestCase):
    """제목이 달라도 같은 고유어·동작을 가진 같은 대학의 같은 사건은 하나로 보여 주고, 애매하면 검토 후보로만 남깁니다."""
    def groups(self,rows):
        return [g for g in public_story_groups(rows) if g['version']==7]

    def test_reworded_reports_of_one_event_group_with_evidence(self):
        rows=[report('a','대구대, 특정구간 전동킥보드 운행 제한…순환버스 운행',school='대구대학교',regions=('경북',)),
              report('b','대구대, 킥보드 사고 위험에 순환버스 도입',source='B',date='2026-11-02T03:00:00+00:00',school='대구대학교',regions=('경북',)),
              report('c','대학가 전동킥보드 퇴출 확산…대구대는 무료 순환버스로 해법 찾는다',source='C',date='2026-11-02T06:00:00+00:00',
                     school='대구대학교',regions=('경북',),category='연구·성과')]
        groups=self.groups(rows)
        self.assertEqual([sorted(g['article_ids']) for g in groups],[['a','b','c']])
        self.assertIn('순환버스',groups[0]['evidence']['shared_entities'])
        self.assertTrue(groups[0]['representative_reason'])

    def test_person_and_action_group_across_word_order(self):
        a=report('a','성균관대, 유지범 총장 연임',school='성균관대학교')
        b=report('b','유지범 성균관대 총장 연임…‘AI 시대 대학 혁신’ 비전 평가',source='B',date='2026-11-02T05:00:00+00:00',school='성균관대학교')
        self.assertEqual([sorted(g['article_ids']) for g in self.groups([a,b])],[['a','b']])

    def test_distinct_events_or_stages_stay_visible(self):
        cases={
            'different events of one anniversary':('동아대, 개교 80주년 기념음악회 개최','동아대, 개교 80주년 기념식 개최'),
            'same organization, different activities':('국립순천대 위험사회 HUSS 사업단, 청년 주도 주민자치 활동 성과 공유',
                                                       '국립순천대 위험사회 HUSS 사업단, AI 융합교육 고도화 위한 대학 간 협력 강화'),
            'announcement and result':('청주대 충북아이돌봄센터, ‘아이돌봄 축제’ 31일 개최','청주대, 5400명 참여 ‘아이돌봄 축제’ 개최…그림대회·가족 골든벨 열려'),
            'different people':('김교흥 의원, 인천대 공공의전원 설립법 발의','인천대 의전원 설립 ‘총력전’…이연주 시의원, 지원 조례 발의'),
            'two stories in one title':('세종대 세종뮤지엄갤러리, 김대열 기획초대전 ‘무상지경’ 개최','세종대, 제14회 학정포럼 개최·김대열 작가 기획초대전 진행'),
            'university only in parentheses':('남자프로배구 대한항공, 이승일·송정민 지명… 윤경(인하대)은 전체 1순위로 OK저축은행행','인하대 배구부 4명 프로 진출…윤경 전체 1순위로 OK저축은행행'),
            'site boilerplate only':('[창업 동아리] 피자파티 참가자 모집 - 전체 행사 - SNU 캘린더 - 서울대 소식','STUDIO2021 기획연주회 - 전체 행사 - SNU 캘린더 - 서울대 소식'),
        }
        schools={'different events of one anniversary':'동아대학교','same organization, different activities':'국립순천대학교',
                 'announcement and result':'청주대학교','different people':'인천대학교','university only in parentheses':'인하대학교',
                 'site boilerplate only':'서울대학교'}
        for name,(first,second) in cases.items():
            with self.subTest(name=name):
                school=schools.get(name,'세종대학교')
                a=report('a',first,school=school);b=report('b',second,source='B',date='2026-11-02T05:00:00+00:00',school=school)
                self.assertEqual(self.groups([a,b]),[])

    def test_other_university_or_distant_dates_stay_visible(self):
        a=report('a','대구대, 킥보드 통제와 순환버스 도입',school='대구대학교')
        self.assertEqual(self.groups([a,report('b','계명대, 킥보드 통제와 순환버스 도입',school='계명대학교',source='B')]),[])
        self.assertEqual(self.groups([a,report('b','대구대, 킥보드 제한하고 순환버스 운영',school='대구대학교',source='B',date='2026-11-06T01:00:00+00:00')]),[])

    def test_blocked_same_entity_pair_becomes_review_candidate(self):
        a=report('a','충남대, 공주대 통합 ‘재추진’ 의결…불씨 살린다',school='충남대학교')
        b=report('b','충남대, 공주대 통합 발표 코앞에서 연기… 재추진 놓고 진통',school='충남대학교',source='B',date='2026-11-02T04:00:00+00:00')
        self.assertEqual(self.groups([a,b]),[])
        candidates=[c for c in duplicate_review_groups([a,b]) if 'evidence' in c]
        self.assertEqual([sorted(c['article_ids']) for c in candidates],[['a','b']])
        self.assertIn('new-fact word differs',candidates[0]['evidence']['blocked_by'])

    def test_summary_must_mention_the_shared_entity(self):
        a=report('a','대구대, 킥보드 통제와 순환버스 도입',school='대구대학교',body='대구대학교가 교내 전동킥보드 운행을 제한하고 무료 순환버스를 도입했다. '*3)
        b=report('b','대구대, 킥보드 제한하고 순환버스 운영',school='대구대학교',source='B',
                 body='대구대학교 총동문회가 장학금 전달식을 열고 재학생 스무 명에게 장학금을 전했다는 다른 소식이다. '*3)
        self.assertEqual(self.groups([a,b]),[])

    def test_existing_groups_are_absorbed_without_double_membership(self):
        rows=[report('a','대구대, 킥보드 통제와 순환버스 도입',school='대구대학교'),
              report('b','대구대, 킥보드 통제와 순환버스 도입',source='B',school='대구대학교',date='2026-11-02T02:00:00+00:00'),
              report('c','대구대, 전동킥보드 운행 제한…무료 순환버스 운영',source='C',school='대구대학교',date='2026-11-02T03:00:00+00:00')]
        groups=public_story_groups(rows)
        members=[i for g in groups for i in g['article_ids']]
        self.assertEqual(len(members),len(set(members)))
        self.assertEqual([(g['version'],sorted(g['article_ids'])) for g in groups],[(7,['a','b','c'])])
        self.assertEqual(groups[0]['evidence']['merged_groups'],[6])


class EventRefinementTests(unittest.TestCase):
    """돌발 사건·장소·숫자·인물 판정과 근거가 약한 기사의 묶음 참여 규칙."""
    def groups(self,rows):
        return [sorted(g['article_ids']) for g in public_story_groups(rows) if g['version']==7]

    def test_incident_report_is_separate_from_event_report(self):
        a=report('a','아일릿 원희·이로하, 발목 부상…연세대 축제 안무 조정 가능성',school='연세대학교')
        b=report('b',"아일릿, 연세대 축제 출격…'취뽀하겠어' 센스 개사",source='B',date='2026-11-02T18:00:00+00:00',school='연세대학교')
        self.assertEqual(self.groups([a,b]),[])
        candidates=[c for c in duplicate_review_groups([a,b]) if 'evidence' in c]
        self.assertEqual([(c['merge_risk'],'incident reported on one side only' in c['evidence']['blocked_by']) for c in candidates],[('high',True)])

    def test_same_incident_family_and_risk_words_are_not_conflicts(self):
        from article_dedup import incidents
        self.assertEqual(incidents('고려대서 20대 남성 현행범 체포'),incidents('고려대 나체 남성 공연음란 혐의 입건'))
        self.assertEqual(incidents('대구대, 킥보드 사고 위험에 순환버스 도입'),frozenset())
        self.assertEqual(incidents('필수의료 붕괴 위기…양산부산대병원 지정 촉구'),frozenset())
        self.assertEqual(incidents("아일릿, ‘체포하겠어’ 떼창"),frozenset())

    def test_number_forms_and_name_lists(self):
        from article_dedup import event_conflicts, named_people
        pairs=[('국립부경대 등록금 시스템 해킹…5천108명 개인정보 유출','국립부경대 등록금 수납시스템 해킹…5108명 개인정보 유출'),
               ('원광대 2026 WON+ 페스티벌 개최',"원광대, ‘2026 WON+ 페스티벌’ 개최…학생 2,000여 명 참여"),
               ('울산과학대 여자축구, U-리그 2위로 시즌 마감…서민정 득점 3위','울산과학대 여자축구부, U-리그 2위로 시즌 마감'),
               ("국립목포대, '세계 상위 2% 과학자'에 김상채·이만승·윤철호·박진우 교수 등재",'국립목포대 이만승‧윤철호 교수 등 4명 선정'),
               ('김인회 인하대 교수, 119번째 헌혈','‘18년간 헌혈 119번’ 김인회 인하대 로스쿨 교수')]
        for first,second in pairs:
            with self.subTest(first=first):
                self.assertEqual(event_conflicts(report('a',first),report('b',second),set()),[])
        self.assertEqual(named_people('도성훈 인천시교육감, 예비교사 격려'),frozenset())
        self.assertEqual(named_people('고려대 조민호 교수, 첫 정년 후 석좌교수'),frozenset({'조민호'}))
        self.assertIn('conflicting numbers',event_conflicts(report('a','세종대 5명 수상'),report('b','세종대 7명 수상'),set()))

    def test_place_name_is_evidence_only_for_agreements(self):
        school='수원대학교'
        a=report('a',"수원대 운영 화성시 어린이급식관리지원센터, '영양의 날' 식생활 캠페인 성료",school=school)
        b=report('b','수원대 운영 화성시 어린이급식관리지원센터, 식생활 교구대여 사업 성료',source='B',school=school)
        self.assertEqual(self.groups([a,b]),[])
        c=report('c','김해시-경상국립대, 농업 분석·연구 협약 체결',school='경상국립대학교')
        d=report('d','김해시·경상국립대, 농업 분석·연구 손잡았다',source='B',school='경상국립대학교')
        self.assertEqual(self.groups([c,d]),[['c','d']])

    def test_short_report_joins_when_it_matches_the_representative_and_majority(self):
        school='성균관대학교'
        rows=[report('a','성균관대 23대 총장에 유지범 현 총장 연임 확정',school=school),
              report('b','유지범 성균관대 총장 연임 확정…2030년까지 23대 총장으로',source='B',school=school),
              report('c','성균관대 이사회, 23대 총장으로 유지범 현 총장 연임 확정',source='C',school=school),
              report('d','성균관대, 유지범 총장 연임',source='D',school=school)]
        self.assertEqual(self.groups(rows),[['a','b','c','d']])

    def test_short_report_with_a_conflict_stays_out(self):
        school='성균관대학교'
        rows=[report('a','성균관대 23대 총장에 유지범 현 총장 연임 확정',school=school),
              report('b','유지범 성균관대 총장 연임 확정…2030년까지 23대 총장으로',source='B',school=school),
              report('c','성균관대 유지범 총장 연임 논란',source='C',school=school)]
        self.assertEqual(self.groups(rows),[['a','b']])

    def test_roundup_title_is_a_digest(self):
        from article_dedup import automatic_merge_exclusion
        self.assertTrue(automatic_merge_exclusion(dict(title="청주시, 청주대에서 '우리 동네 영화관' 개최 외 (10월29일 종합)")))
        self.assertFalse(automatic_merge_exclusion(dict(title='청주대, 우리 동네 영화관 개최(종합)')))


class GeneralArticleGroupingTests(unittest.TestCase):
    """대학명도 첫머리 기관도 없는 일반 기사끼리의 같은 주제 묶음."""
    def general(self,ident,title,date='2026-11-04T01:00:00+00:00',source=None):
        return dict(id=ident,title=title,source=source or ident,date=date,school='대학명 미확인',school_names=[],regions=[],
                    region='',category='행사·특강',body='',url='https://example.org/'+ident)

    def groups(self,rows):
        return [sorted(g['article_ids']) for g in public_story_groups(rows) if g['version']==7]

    def test_same_named_event_groups_even_when_shortened(self):
        rows=[self.general('a','대전시, 2026 대학만화웹툰대전·웹툰채용박람회 개최'),
              self.general('b','대학만화웹툰대전 & 웹툰채용박람회 개최',date='2026-11-04T02:00:00+00:00'),
              self.general('c','대학생·신진작가 웹툰산업 진출 지원…전국 웹툰대전 개최',date='2026-11-04T03:00:00+00:00')]
        self.assertEqual(self.groups(rows),[['a','b','c']])

    def test_same_kind_event_in_different_places_stays_separate(self):
        for first,second in (('담양군, 제19기 농업인대학 졸업식 개최','진주시, 2026년도 농업인대학 졸업식 개최'),
                             ('(재)상주시장학회, 2028학년도 대학 입시설명회 개최','송파구, 고1·2 학부모 대상 대학입시설명회 개최'),
                             ('대한적십자사 강원지사, 대학RCY 캠프 성료','적십자사 울산지사-대학RCY, 봉사자 나눔')):
            with self.subTest(first=first):
                self.assertEqual(self.groups([self.general('a',first),self.general('b',second)]),[])

    def test_place_names_short_overlaps_and_notices_are_not_evidence(self):
        for first,second in (('인천시·인천TP, 대학 출신 창업기업 투자유치 지원','인천시립박물관, 박물관대학 세 번째 강의'),
                             ('AI에 맡길 일 아는 관리자, 더 나은 대학 행정 만든다','전국대학평생교육원관리자협, 하반기 세미나'),
                             ('이상일 용인시장, 이탈리아 기업 캠퍼스 방문','이탈리아서 열린 미국 대학 농구 교황 더비'),
                             ('[알립니다] 제18회 한국대학신문 대학직원대상 공모','한림학보사, 2026 대학신문 생명존중 기사공모전 우수상'),
                             ('한국대학신문 대학직원대상 후보 추천','한국대학바둑연맹 소속 대학생, 기념관 방문')):
            with self.subTest(first=first):
                self.assertEqual(self.groups([self.general('a',first),self.general('b',second)]),[])

    def test_general_articles_do_not_change_university_rarity(self):
        # 일반 기사에 같은 말이 나와도 대학 기사 고유어가 흔한 말로 바뀌지 않습니다.
        school=[report('a','대구가톨릭대, 대구·경북 대학페스타 2년 연속 종합우승',school='대구가톨릭대학교'),
                report('b','대구가톨릭대, 대학페스타 2년 연속 정상…우승 상금 기부',source='B',school='대구가톨릭대학교')]
        others=[self.general('g%d'%n,'동성로서 2026 대구·경북 대학페스타 개최 %d'%n) for n in range(3)]
        groups=[sorted(g['article_ids']) for g in public_story_groups(school+others) if set(g['article_ids'])&{'a','b'}]
        self.assertEqual(groups,[['a','b']])


class IdenticalTitleRefinementTests(unittest.TestCase):
    def test_hyphen_inside_title_is_not_a_publisher_tail(self):
        from article_dedup import title_identity
        a=report('a',"강원도립대, ‘2026 강원 창업 POP-UP 콘서트’ 개최",school='강원도립대학교')
        b=report('b',"강원도립대, ‘2026 강원 창업 POP-UP 콘서트’ 서울서 개최",school='강원도립대학교')
        self.assertNotEqual(title_identity(a),title_identity(b))
        self.assertEqual(title_identity(report('c','세종대 학정포럼 개최 - 머니투데이')),title_identity(report('d','세종대 학정포럼 개최')))

    def test_short_words_inside_longer_words_do_not_exclude(self):
        from article_dedup import automatic_merge_exclusion
        self.assertFalse(automatic_merge_exclusion(dict(title="삼육대 권소연 박사과정생, '이공계 박사우수장학생' 선발")))
        self.assertTrue(automatic_merge_exclusion(dict(title='총장 사과 입장 발표')))

    def test_long_specific_title_republished_days_later_groups(self):
        title="성균관대 앵커사업단, 경기도 양자·AI 유망 기술기업 투자유치·사업화 지원 나선다"
        a=report('a',title,school='성균관대학교',date='2026-10-28T14:00:00+00:00')
        b=report('b',title,source='B',school='성균관대학교',date='2026-11-01T15:00:00+00:00')
        self.assertEqual([sorted(g['article_ids']) for g in public_story_groups([a,b]) if g['version']==6],[['a','b']])
        c=report('c','세종대 학정포럼 개최',date='2026-10-28T14:00:00+00:00')
        d=report('d','세종대 학정포럼 개최',source='B',date='2026-11-01T15:00:00+00:00')
        self.assertEqual([g for g in public_story_groups([c,d]) if g['version']==6],[])

    def test_label_with_specific_content_is_compared(self):
        a=report('a','[동정] 중앙대광명병원 윤수미 교수, 진단검사의학회 우수구연상 수상',school='중앙대학교')
        b=report('b','중앙대광명병원 윤수미 교수, 진단검사의학회 ‘우수구연상’ 수상',source='B',school='중앙대학교')
        self.assertEqual([sorted(g['article_ids']) for g in public_story_groups([a,b]) if g['version']==6],[['a','b']])
        c=report('c','[인사] 경북대학교',school='경북대학교');e=report('e','[인사] 경북대학교',source='B',school='경북대학교')
        self.assertEqual(public_story_groups([c,e]),[])


if __name__=='__main__':
    unittest.main()
