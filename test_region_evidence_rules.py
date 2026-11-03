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

    def test_main_campus_default_records_method(self):
        for title,region in (('성균관대 유지범 총장 연임','서울'),('연세대 연구팀 기술 개발','서울'),('고려대 교수팀 논문','서울'),
                             ('전남대 교수 임용','광주'),('단국대 장학금 수여식','경기도'),('영산대 드론 대회 수상','경남')):
            row=classify(title)
            self.assertEqual(row['regions'],[region],title)
            self.assertEqual(row['classification_method'],'main_campus_default',title)
            self.assertEqual(row['universities'][0]['region_resolution'],'main_campus_default',title)
            self.assertEqual(len(row['universities'][0]['addresses']),1,title)
            self.assertGreater(len(row['universities'][0]['candidate_regions']),1,title)

    def test_explicit_campus_wins_over_main_campus(self):
        row=classify('고려대 세종캠퍼스 연구')
        self.assertEqual((row['regions'],row['classification_method']),(['세종'],'campus_location'))

    def test_uncertain_articles_stay_for_review(self):
        for title in ('성균관대·연세대 공동 연구','을지대의료원 창립 70주년 심포지엄','을지대병원 개원 기념식','고려대, 제주서 포럼 개최'):
            row=classify(title)
            self.assertEqual(row['regions'],[],title)
            self.assertEqual(row['classification_method'],'review_required',title)
            self.assertEqual(row['classification_status'],'needs_review',title)

    def test_two_campus_places_stay_unresolved(self):
        self.assertEqual(classify('[원주소식] 연세대 송도 학생 교류')['regions'],[])
        self.assertEqual(classify('전남광주 포럼, 전남대서 개최')['regions'],[])

    def test_partner_or_venue_never_confirms_university_location(self):
        self.assertEqual(classify('김해댕댕파크, 인제대 실습 거점으로')['classification_method'],'main_campus_default')
        for title in ('인제대, 부산 기관과 협약','경동대 앵커사업단, 양주시상공회와 업무협약','수원시 기업 대표, 성균관대 특강',
                      '영산대 교수, 부산서 K푸드 체험','국가유산청, 동국대와 경주 공동발굴'):
            row=classify(title)
            self.assertEqual((row['regions'],row['classification_method']),([],'review_required'),title)

    def test_verified_units_override_main_campus(self):
        for title,region in (('명지대 아랍지역학과, 청년교류','서울'),('상명대 국어문화원, 공동 연수회','충남'),
                             ('영산대 도예디자인학과 13명 수상','부산'),('영산대 조리전공 교수, 부산서 체험','부산'),
                             ('한국이콜랩, 연세대 K-NIBRT와 인력 양성','인천'),('전남대 문사대, 지역 콘텐츠 발굴','전남')):
            row=classify(title)
            self.assertEqual((row['regions'],row['classification_method']),([region],'campus_location'),title)
            self.assertTrue(row['universities'][0]['campus_cue_evidence'],title)

    def test_unverified_or_parallel_campus_school_is_not_defaulted(self):
        for title in ('명지대 연구 발표','명지대학교 행정학과 교수 발언'):
            row=classify(title)
            self.assertEqual((row['regions'],row['classification_method']),([],'review_required'),title)

    def test_common_words_and_sports_clubs_are_not_places(self):
        for title,region in (('연세대 교원 연수 프로그램 운영','서울'),('동작 인식 기술, 중앙대 연구팀 개발','서울'),
                             ('수원FC 위민, 성균관대 미드필더 영입','서울'),('영산대, 드론 양산 체제 구축','경남')):
            row=classify(title)
            self.assertEqual((row['regions'],row['classification_method']),([region],'main_campus_default'),title)
        self.assertEqual(campus_place_names('인천광역시 연수구 송도과학로 85'),['연수구','송도'])

    def test_other_university_name_is_not_a_place(self):
        self.assertEqual(classify('성균관대·수원대 공동 연구')['universities'][0]['region_resolution'],'campus_unspecified')

    def test_summary_only_counts_road_places_beside_the_university(self):
        self.assertEqual(classify('인제대 연구 발표','인제대는 김해 지역 기업과 협의했다.')['classification_method'],'main_campus_default')
        self.assertEqual(classify('전남대 학술제 개최','행사장은 용봉관이다.')['classification_method'],'main_campus_default')
        row=classify('전남대 학술제 개최','전남대는 용봉동 일대에서 학술제를 연다.')
        self.assertEqual((row['regions'],row['classification_method']),(['광주'],'campus_location'))


class ArticleEvidenceTests(unittest.TestCase):
    def test_title_region_does_not_confirm_campus(self):
        self.assertEqual(classify('인제대, 경남 G-NEX 참가')['classification_method'],'main_campus_default')
        self.assertEqual(classify('상명대, 충청남도 공동 연수회')['classification_method'],'review_required')

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

    def test_main_campus_default_fills_existing_but_uncertain_does_not(self):
        old=self.blank('성균관대 유지범 총장 연임')
        self.assertTrue(verified_unknown_fill(old,reclassify_article(old)))
        for title in ('성균관대·연세대 공동 연구','을지대의료원 창립 70주년 심포지엄'):
            old=self.blank(title)
            self.assertFalse(verified_unknown_fill(old,reclassify_article(old)),title)

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
