import unittest
from publication_safety import verified_unknown_fill
from university_regions import campus_place_names, reclassify_article


def classify(title,body='',source=''):
    return reclassify_article(dict(id='test',title=title,body=body,url='https://example.com/a',source=source))


class CampusPlaceTests(unittest.TestCase):
    def test_address_place_selects_one_campus(self):
        for title,region,resolution in [
                ('[양주소식]경동대 취업박람회','경기도','campus_place_match'),
                ('전남대 대학원, 용봉학술제 개최','광주','campus_place_match'),
                ('송도 세브란스병원 시공계약, 연세대 이사회','인천','campus_place_match')]:
            row=classify(title)
            self.assertEqual(row['regions'],[region],title)
            self.assertEqual(row['universities'][0]['region_resolution'],resolution,title)
            self.assertTrue(row['universities'][0]['campus_place_evidence'],title)
            self.assertTrue(row['universities'][0]['addresses'],title)

    def test_unspecified_campus_shows_every_confirmed_campus_region(self):
        for title,regions in (('성균관대 유지범 총장 연임',['경기도','서울']),('연세대 연구팀 기술 개발',['강원','서울','인천']),
                              ('전남대 교수 임용',['광주','전남']),('명지대 연구 발표',['경기도','서울']),('영산대 드론 대회 수상',['경남','부산'])):
            row=classify(title)
            self.assertEqual((row['regions'],row['classification_method'],row['classification_confidence']),(regions,'multi_campus_estimate','estimated'),title)
            self.assertEqual(row['universities'][0]['region_resolution'],'campus_candidates',title)
            self.assertEqual(len(row['universities'][0]['addresses']),len(regions),title)

    def test_explicit_campus_wins_over_main_campus(self):
        row=classify('고려대 세종캠퍼스 연구')
        self.assertEqual((row['regions'],row['classification_method'],row['classification_confidence']),(['세종'],'campus_location','confirmed'))

    def test_unidentified_hospital_stays_for_review(self):
        for title in ('을지대의료원 창립 70주년 심포지엄','을지대병원 개원 기념식','고려대병원 행사'):
            row=classify(title)
            self.assertEqual((row['regions'],row['classification_method'],row['classification_status']),([],'review_required','needs_review'),title)

    def test_multiple_universities_show_all_related_regions(self):
        row=classify('성균관대·연세대 공동 연구')
        self.assertEqual(row['regions'],['강원','경기도','서울','인천'])
        self.assertEqual(row['classification_confidence'],'estimated')
        row=classify('숭실대·고려대 세종캠퍼스 공동 연구')
        self.assertEqual((row['regions'],row['classification_confidence']),(['서울','세종'],'confirmed'))

    def test_article_region_outside_campuses_is_recorded_for_review(self):
        row=classify('고려대, 제주서 포럼 개최')
        self.assertEqual(row['regions'],['서울','세종'])
        self.assertEqual(row['region_review_reasons'],['대학 소재지와 기사 지역 불일치'])

    def test_two_campus_places_stay_unresolved(self):
        self.assertEqual(classify('[원주소식] 연세대 송도 학생 교류')['regions'],['강원','서울','인천'])
        self.assertEqual(classify('전남광주 포럼, 전남대서 개최')['regions'],['광주','전남'])

    def test_partner_or_venue_never_confirms_university_location(self):
        for title in ('김해댕댕파크, 인제대 실습 거점으로','인제대, 부산 기관과 협약','경동대 앵커사업단, 양주시상공회와 업무협약',
                      '수원시 기업 대표, 성균관대 특강','영산대 교수, 부산서 K푸드 체험','국가유산청, 동국대와 경주 공동발굴'):
            row=classify(title)
            self.assertEqual(row['classification_method'],'multi_campus_estimate',title)
            self.assertEqual(set(row['regions']),set(row['universities'][0]['candidate_regions']),title)

    def test_verified_units_override_main_campus(self):
        for title,region in (('명지대 아랍지역학과, 청년교류','서울'),('상명대 국어문화원, 공동 연수회','충남'),
                             ('영산대 도예디자인학과 13명 수상','부산'),('영산대 조리전공 교수, 부산서 체험','부산'),
                             ('한국이콜랩, 연세대 K-NIBRT와 인력 양성','인천'),('전남대 문사대, 지역 콘텐츠 발굴','전남')):
            row=classify(title)
            self.assertEqual((row['regions'],row['classification_method']),([region],'campus_location'),title)
            self.assertTrue(row['universities'][0]['campus_cue_evidence'],title)

    def test_unverified_department_does_not_pick_a_campus(self):
        row=classify('명지대학교 행정학과 교수 발언')
        self.assertEqual((row['regions'],row['classification_method']),(['경기도','서울'],'multi_campus_estimate'))

    def test_common_words_and_sports_clubs_are_not_places(self):
        for title in ('연세대 교원 연수 프로그램 운영','동작 인식 기술, 중앙대 연구팀 개발',
                      '수원FC 위민, 성균관대 미드필더 영입','영산대, 드론 양산 체제 구축'):
            row=classify(title)
            self.assertEqual(row['classification_method'],'multi_campus_estimate',title)
        self.assertEqual(campus_place_names('인천광역시 연수구 송도과학로 85'),['연수구','송도'])

    def test_other_university_name_is_not_a_place(self):
        self.assertEqual(classify('성균관대·수원대 공동 연구')['universities'][0]['region_resolution'],'campus_candidates')

    def test_summary_only_counts_road_places_beside_the_university(self):
        self.assertEqual(classify('인제대 연구 발표','인제대는 김해 지역 기업과 협의했다.')['classification_method'],'multi_campus_estimate')
        self.assertEqual(classify('전남대 학술제 개최','행사장은 용봉관이다.')['classification_method'],'multi_campus_estimate')
        row=classify('전남대 학술제 개최','전남대는 용봉동 일대에서 학술제를 연다.')
        self.assertEqual((row['regions'],row['classification_method']),(['광주'],'campus_location'))


class ArticleEvidenceTests(unittest.TestCase):
    def test_title_region_does_not_confirm_campus(self):
        self.assertEqual(classify('인제대, 경남 G-NEX 참가')['classification_method'],'multi_campus_estimate')
        self.assertEqual(classify('상명대, 충청남도 공동 연수회')['regions'],['서울','충남'])  # 행사 지역은 캠퍼스를 확정하지 않습니다.

    def test_hospital_campus(self):
        self.assertEqual(classify('인제대학교 부산백병원, 의료봉사')['regions'],['부산'])
        self.assertEqual(classify('한양대 구리 황선진 교수 선정')['regions'],['경기도'])

    def test_official_publisher_variants(self):
        row=classify('월영소식',source='경남대학교 대표')
        self.assertEqual((row['school_names'],row['regions']),(['경남대학교'],['경남']))
        self.assertEqual(classify('[미디어] 작가 전시',source='경희대학교 미디어센터')['school_names'],['경희대학교'])
        self.assertEqual(classify('월영소식',source='한국대학신문')['school_names'],[])

    def test_municipal_institution_in_title(self):
        self.assertEqual(classify("평택시의회 '삼성전자 평택캠퍼스' 현장 시찰")['regions'],['경기도'])
        self.assertEqual(classify('군산소방서, 건립 현장 사고 대응 교육')['regions'],['전북'])
        self.assertEqual(classify('여수교육지원청, 지역 진로 축제')['regions'],['전남'])
        self.assertEqual(classify('고성군 농촌대학 졸업식')['regions'],[])  # 강원·경남 동명 지자체

    def test_region_policy_forms(self):
        self.assertEqual(classify('대학과 손잡은 충남형 돌봄, 1500명 참여')['regions'],['충남'])
        self.assertEqual(classify('부산광역시의회 대학생 모의 의회')['regions'],['부산'])
        self.assertEqual(classify('심평원 강원본부, 하천 환경보호 활동')['regions'],['강원'])
        self.assertEqual(classify('전남광주시의회, 대학생 모의의회 첫 개원')['regions'],['광주','전남'])


class SoonchunhyangHospitalTests(unittest.TestCase):
    def test_each_hospital_uses_its_own_address(self):
        for title,region in (('순천향대서울병원, 병동 오픈','서울'),('순천향대 부천병원, 당뇨발의 날 행사','경기도'),
                             ('순천향대학교 부속 구미병원 개원 기념식','경북'),('순천향대천안병원, 평가 1등급','충남')):
            row=classify(title)
            self.assertEqual((row['regions'],row['classification_method']),([region],'campus_location'),title)
            self.assertEqual(row['universities'][0]['affiliation_type'],'university_hospital',title)

    def test_two_hospitals_keep_both_regions(self):
        self.assertEqual(classify('순천향대 서울병원·부천병원 공동 캠페인')['regions'],['경기도','서울'])


class NoUniversityStoryTests(unittest.TestCase):
    def test_same_institution_event_groups_without_university(self):
        from article_dedup import public_story_groups
        rows=[]
        for i,title in enumerate(('충남교육청, 대학 연계 ‘온돌봄 캠프’ 성황…학생·학부모 1,500여 명 참여',
                                  '충남교육청, 대학과 손잡고 온돌봄 캠프 열어…학생·학부모 1,500여 명 참여',
                                  '충남교육청, 대학·교육지원청과 온돌봄 협력 강화')):
            row=classify(title);row.update(id=str(i),date='2026-11-01T0%d:00:00+00:00'%i,source='S%d'%i,url='https://example.com/%d'%i)
            rows.append(row)
        self.assertEqual(rows[0]['regions'],['충남'])
        groups=[g for g in public_story_groups(rows) if g['version']==5]
        self.assertEqual([sorted(g['article_ids']) for g in groups],[['0','1']])

    def test_program_is_not_shown_as_university(self):
        row=classify("김천시, 40년 전통의 '제42기 김천시여성대학' 화려한 개강")
        self.assertEqual((row['school'],row['school_names'],row['regions']),('대학명 미확인',[],['경북']))
        self.assertEqual(row['education_programs'][0]['name'],'김천시여성대학')
        row=classify('전남광주특별시 동구 여성대학, 직업교육 수료생 2명 취업 성과')
        self.assertEqual((row['school'],row['regions']),('대학명 미확인',['광주','전남']))

    def test_chamber_of_commerce_region(self):
        self.assertEqual(classify('대전상의, 지역대학과 손잡고 청년 취업 지원 나서')['regions'],['대전'])

    def test_national_scope_is_not_unclassified(self):
        for title in ('한국폴리텍대학, 직업교육과정 5천590명 모집','폴리텍대학, 현장 안전 핸드북 전국 배포','전국 대학 총장 협의회 개최'):
            row=classify(title)
            self.assertEqual((row['regions'],row['classification_method']),(['전국'],'national_scope'),title)
        self.assertEqual(classify('영천시·한국폴리텍대학 로봇산업 업무협약')['regions'],[])

    def test_polytechnic_spellings_and_campus(self):
        for title,region in (('폴리텍Ⅳ 캡스톤 경진대회…청주캠퍼스서 대상 수상','충북'),
                             ('영천시-한국폴리텍대학, 정주형 인재 양성·로봇캠퍼스 협력','경북'),('한국폴리텍 대전캠, 금상','대전')):
            row=classify(title)
            self.assertEqual((row['regions'],row['classification_method']),([region],'campus_location'),title)


class CampusNameLinkTests(unittest.TestCase):
    def test_campus_name_matches_address_of_one_campus(self):
        for title,region in (('경찰, 고려대 안암캠퍼스 활보 남성 체포','서울'),('고려대 서울 안암캠퍼스서 행사','서울'),
                             ('고려대 세종캠퍼스 연구','세종'),('중앙대 흑석캠퍼스 축제','서울')):
            row=classify(title)
            self.assertEqual((row['regions'],row['classification_confidence']),([region],'confirmed'),title)
            self.assertTrue(row['universities'][0]['addresses'],title)

    def test_spaced_modifier_is_not_a_campus_name(self):
        row=classify('옷 다 벗고 고려대 활보…대낮 캠퍼스에 나타난 20대')
        self.assertEqual((row['regions'],row['classification_method']),(['서울','세종'],'multi_campus_estimate'))
        self.assertEqual(classify('청운대, 바비큐축제 연계 캠퍼스 캠핑장 성료')['regions'],['충남'])
        self.assertEqual(classify('인천대학교, 문일여고 360여 명 초청 캠퍼스 탐방')['regions'],['인천'])

    def test_unlisted_campus_of_single_region_university(self):
        # 띄어 쓴 '서울주 캠퍼스'는 캠퍼스명으로 보지 않아 울산대의 단일 소재지로 분류됩니다.
        self.assertEqual(classify("울산대, UbiCam 6호 ‘서울주 캠퍼스’ 조성")['regions'],['울산'])
        for title,region in (("계명대 성서캠퍼스에서 AI 비전 선포",'대구'),("울산대 거점형 멀티캠퍼스 '유비캠' 6호 조성",'울산')):
            row=classify(title)
            self.assertEqual((row['regions'],row['classification_confidence']),([region],'estimated'),title)
            self.assertEqual(row['universities'][0]['addresses'],[],title)

    def test_unlisted_campus_of_single_region_university_fills_existing_rows(self):
        from publication_safety import verified_unknown_fill
        old=dict(id='a',title="계명대 AI 대전환 선언",body='계명대가 성서캠퍼스에서 AI 비전 선포식을 열었다.',url='https://example.com/a',regions=[])
        self.assertTrue(verified_unknown_fill(old,reclassify_article(old)))

    def test_unlisted_campus_of_multi_campus_university_is_not_guessed(self):
        row=classify('한양대 알수없음캠퍼스 연구 발표')
        self.assertEqual(row['regions'],[])

    def test_campus_name_of_another_university_is_not_used(self):
        row=classify('고려대·중앙대 공동 연구, 흑석캠퍼스에서 발표')
        schools={u['name']:u['regions'] for u in row['universities']}
        self.assertEqual(schools['중앙대학교'],['서울'])
        self.assertEqual(schools['고려대학교'],['서울','세종'])

    def test_named_hospitals(self):
        self.assertEqual(classify('인제대 해운대백병원, 평가 1등급')['regions'],['부산'])
        self.assertEqual(classify('연세대 용인세브란스병원, 건강강좌 개최')['regions'],['경기도'])


class UnlistedCampusGuardTests(unittest.TestCase):
    def test_gachon_medical_campus_is_incheon(self):
        row=classify("인천시, 가천대 메디컬캠퍼스서 '전국 인설 차문화전' 개최")
        self.assertEqual((row['regions'],row['classification_confidence']),(['인천'],'confirmed'))
        self.assertEqual(classify('가천대 글로벌캠퍼스 축제')['regions'],['경기도'])
        self.assertEqual(classify('가천대 연구팀 기술 개발')['regions'],['경기도','인천'])

    def test_separate_campus_words_are_not_given_the_main_region(self):
        for title in ('계명대 메디컬캠퍼스 개소','동아대 글로벌캠퍼스 행사','울산대 제2캠퍼스 조성'):
            self.assertEqual(classify(title)['regions'],[],title)

    def test_place_name_of_another_region_is_not_given_the_main_region(self):
        self.assertEqual(classify('계명대 송도캠퍼스 개교')['regions'],[])
        self.assertEqual(classify('계명대 성서캠퍼스 행사')['regions'],['대구'])

    def test_other_region_in_article_blocks_single_region_guess(self):
        self.assertEqual(classify('부산시, 계명대 성서캠퍼스와 행사')['regions'],[])


class TitleRevisionTests(unittest.TestCase):
    def test_confirmed_version_wins_when_inside_the_other_estimate(self):
        from publication_safety import version_decision, verified_unknown_fill
        old=dict(id='a',title='고려대 안암캠퍼스 내부에 20대 나체남 출몰',body='',url='https://example.com/a',regions=[])
        raw=dict(old,pending_update=dict(title='연세대 이어 이번엔 고려대…대낮 캠퍼스 알몸 활보한 20대男'))
        self.assertEqual(version_decision(old,raw)['regions'],['서울'])
        self.assertTrue(verified_unknown_fill(old,version_decision(old,raw),raw))

    def test_conflicting_versions_are_not_filled(self):
        from publication_safety import version_decision, verified_unknown_fill
        old=dict(id='a',title='고려대 세종캠퍼스 행사',body='',url='https://example.com/a',regions=[])
        raw=dict(old,pending_update=dict(title='고려대 안암캠퍼스 행사'))
        self.assertIsNone(version_decision(old,raw))
        self.assertFalse(verified_unknown_fill(old,reclassify_article(old),raw))

    def test_url_change_is_not_treated_as_same_article(self):
        from publication_safety import version_decision
        old=dict(id='a',title='고려대 안암캠퍼스 행사',body='',url='https://example.com/a',regions=[])
        raw=dict(old,pending_update=dict(title='고려대 세종캠퍼스 행사',url='https://example.com/b'))
        self.assertEqual(version_decision(old,raw)['regions'],['서울'])


class ConsistencyPolicyTests(unittest.TestCase):
    def test_school_level_rows_widen_after_directory_change(self):
        from publication_safety import estimate_policy_update
        old=dict(id='a',title='가천대 반도체 아카데미 21명 수료',body='',url='https://example.com/a',regions=['경기도'],
                 universities=[dict(name='가천대학교',campus_status='not_specified')])
        self.assertTrue(estimate_policy_update(old,reclassify_article(old)))
        foreign=dict(old,title='명지대 대학원생 미국 연수 선정',regions=['해외'],universities=[dict(name='명지대학교',campus_status='not_specified')])
        self.assertTrue(estimate_policy_update(foreign,reclassify_article(foreign)))

    def test_rows_with_campus_or_hospital_evidence_are_not_widened(self):
        from publication_safety import estimate_policy_update
        old=dict(id='a',title='가천대 반도체 아카데미 수료',body='',url='https://example.com/a',regions=['경기도'],
                 universities=[dict(name='가천대학교',campus_status='matched',campus_names=['글로벌캠퍼스'])])
        self.assertFalse(estimate_policy_update(old,reclassify_article(old)))

    def test_campus_place_evidence_corrects_school_level_region(self):
        from publication_safety import verified_campus_correction
        old=dict(id='a',title="전남대 대학원, 연구성과 나누는 ‘2026 용봉학술제’ 개최",body='',url='https://example.com/a',regions=['광주','전남'])
        self.assertTrue(verified_campus_correction(old,reclassify_article(old)))
        mention=dict(old,title='경기도, 청소년과 함께 서울대학교 탐방',regions=['경기도','서울'])
        self.assertFalse(verified_campus_correction(mention,reclassify_article(mention)))


class ExistingCorrectionTests(unittest.TestCase):
    def row(self,title,regions):
        return dict(id='a',title=title,body='',url='https://example.com/a',regions=regions)

    def test_school_level_region_is_corrected_by_official_location(self):
        from publication_safety import verified_campus_correction
        for title,old in (('순천향대서울병원, 병동 오픈',['충남']),('건국대병원, 수술 6000건',['서울','충북']),('한양대 ERICA 연구 발표',['경기도','서울'])):
            item=self.row(title,old)
            self.assertTrue(verified_campus_correction(item,reclassify_article(item)),title)

    def test_no_correction_without_campus_evidence_or_when_region_is_in_article(self):
        from publication_safety import verified_campus_correction
        for title,old in (('성균관대 총장 연임',['경기도','서울']),('서울 기관, 분당서울대병원과 연구',['서울']),
                          ('을지대의료원 심포지엄',['대전']),('순천향대천안병원 평가 1등급',['충남'])):
            item=self.row(title,old)
            self.assertFalse(verified_campus_correction(item,reclassify_article(item)),title)


class ExistingArticleFillTests(unittest.TestCase):
    def blank(self,title,**extra):
        return dict(id='a',title=title,body='',url='https://example.com/a',regions=[],**extra)

    def test_fill_with_place_and_municipality_evidence(self):
        for title in ('서대문소방서, 연세대 과학원서 훈련',"평택시의회 '삼성전자 평택캠퍼스' 현장 시찰"):
            old=self.blank(title)
            self.assertTrue(verified_unknown_fill(old,reclassify_article(old)),title)

    def test_estimate_fills_existing_but_unidentified_hospital_or_conflict_does_not(self):
        for title in ('성균관대 유지범 총장 연임','성균관대·연세대 공동 연구','명지대 교수테니스회 우승','폴리텍대학, 현장 안전 핸드북 전국 배포'):
            old=self.blank(title)
            self.assertTrue(verified_unknown_fill(old,reclassify_article(old)),title)
        for title in ('을지대의료원 창립 70주년 심포지엄','고려대, 제주서 포럼 개최'):
            old=self.blank(title)
            self.assertFalse(verified_unknown_fill(old,reclassify_article(old)),title)

    def test_earlier_main_campus_guess_is_widened_not_replaced(self):
        from publication_safety import estimate_policy_update
        old=dict(self.blank('성균관대 유지범 총장 연임'),regions=['서울'],classification_method='main_campus_default')
        self.assertTrue(estimate_policy_update(old,reclassify_article(old)))
        self.assertFalse(estimate_policy_update(dict(old,classification_method='campus_location'),reclassify_article(old)))

    def test_no_fill_when_proposal_differs_or_regions_exist(self):
        old=self.blank('서대문소방서, 연세대 과학원서 훈련')
        self.assertFalse(verified_unknown_fill(old,dict(regions=['부산'])))
        self.assertFalse(verified_unknown_fill(dict(old,regions=['서울']),reclassify_article(old)))

    def test_no_fill_from_summary_only_or_foreign_region(self):
        old=dict(self.blank('대학 혁신 논의'),body='경남에서 포럼이 열렸다.')
        self.assertFalse(verified_unknown_fill(old,reclassify_article(old)))
        old=self.blank('美플로리다 대학 총격')
        self.assertFalse(verified_unknown_fill(old,dict(regions=['해외'])))


if __name__=='__main__':
    unittest.main()
