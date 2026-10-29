"""네트워크 없이: python -m unittest discover -s university-hub -p test_rss.py"""
import unittest
from rss_collector import parse_date, parse_feed
from university_regions import match_universities, reclassify_article


class FeedTests(unittest.TestCase):
    def test_district_foundation_has_region_but_no_invented_university(self):
        row=reclassify_article(dict(title='강북구 꿈나무키움 장학재단, 재능장학생 선발',body=''))
        self.assertEqual(row['regions'],['서울'])
        self.assertEqual(row['school_names'],[])

    def test_national_rename_is_not_ambiguous(self):
        for title in ['한밭대 백수정 교수 연구 성과','국립한밭대학교 연구 소식','한밭대학교 학생 소식']:
            row=reclassify_article(dict(title=title,body=''))
            self.assertEqual(row['school_names'],['국립한밭대학교'])
            self.assertIn('대전',row['regions'])

    def test_polytechnic_name_without_campus_is_still_identified(self):
        row=reclassify_article(dict(title='두원에너지 대표, 한국폴리텍대학 장학금 기탁',body=''))
        self.assertEqual(row['school_names'],['한국폴리텍대학'])
        self.assertEqual(row['regions'],[])
        self.assertEqual(row['universities'][0]['method'],'national_network')
        row=reclassify_article(dict(title='한국폴리텍대학 장학금 전달',body='한국폴리텍대학 대전캠퍼스에서 기탁식을 개최했다.'))
        self.assertEqual(row['regions'],['대전'])
        self.assertNotIn('한국폴리텍대학',row['school_names'])

    def test_policy_slogan_is_not_seoul_university(self):
        row=reclassify_article(dict(title='서울대10개 만들기…한림대·울산대 지방 사립대 네트워크 추진',body=''))
        self.assertNotIn('서울대학교',row['school_names'])
        self.assertNotIn('서울',row['regions'])
        self.assertIn('강원',row['regions'])
        self.assertIn('울산',row['regions'])
        self.assertEqual(reclassify_article(dict(title='서울대, 10개 연구팀 선정',body=''))['school'],'서울대학교')

    def test_general_campus_words_and_shared_campus(self):
        row=reclassify_article(dict(title='안양대, 축제 개막…사흘간 캠퍼스 대축제',body=''))
        self.assertIn('경기도',row['regions'])
        self.assertNotEqual(row['universities'][0]['campus_status'],'unresolved')
        row=reclassify_article(dict(title='서울대·충남대 한곳에 모인 세종공동캠퍼스',body=''))
        self.assertEqual(row['regions'],['세종'])
        self.assertTrue(all(u['regions']==['세종'] for u in row['universities']))

    def test_foreign_homonyms_do_not_get_domestic_address(self):
        row=reclassify_article(dict(title='한성대, 우즈베키스탄 대학과 협약',body='타슈켄트 아주대와 협약을 체결했다.'))
        self.assertNotIn('아주대학교',row['school_names'])
        self.assertNotIn('경기도',row['regions'])
        row=reclassify_article(dict(title='하노이 산업대학교와 국제대학교(VNU-HCM)가 협력 협정 체결',body=''))
        self.assertEqual(row['regions'],['해외'])
        self.assertNotIn('국제대학교',row['school_names'])
        row=reclassify_article(dict(title='상하이 교통대 연구 발표',body=''))
        self.assertNotIn('국립한국교통대학교',row['school_names'])
        row=reclassify_article(dict(title='제주한라대-마카오관광대 국제캠퍼스 구축',body=''))
        self.assertIn('해외',row['regions'])

    def test_named_regional_public_education_institutions(self):
        for title,region in [('부산박물관 박물관대학 개최','부산'),('경기 귀농귀촌대학 수료식','경기도')]:
            row=reclassify_article(dict(title=title,body=''))
            self.assertIn(region,row['regions'])

    def test_verified_abbreviations_and_national_name(self):
        for title,name,region in [('인하공전, 학생 진로 특강','인하공업전문대학','인천'),
                                  ('국립인천대학교 앵커사업단 소식','인천대학교','인천'),
                                  ('교통대 총장 글로컬대학 관련 발언','국립한국교통대학교','충북')]:
            row=reclassify_article(dict(title=title,body=''))
            self.assertEqual(row['school'],name)
            self.assertIn(region,row['regions'])

    def test_university_hospital_uses_own_location(self):
        for title,name,region in [('분당서울대학교병원 연구성과','서울대학교','경기도'),
                                  ('화순전남대학교병원 연구성과','전남대학교','전남'),
                                  ('칠곡경북대학교병원 교수 수상','경북대학교','대구'),
                                  ('양산부산대학교병원 진료 안내','부산대학교','경남'),
                                  ('세종충남대학교병원 소식','충남대학교','세종'),
                                  ('강동경희대학교병원 건강강좌','경희대학교','서울')]:
            row=reclassify_article(dict(title=title,body=''))
            self.assertEqual(row['school'],name)
            self.assertEqual(row['regions'],[region])

    def test_participants_and_news_rubrics_are_not_subjects(self):
        row=reclassify_article(dict(title='동의과학대 베트남 유학생 자동차정비기능사 합격',body=''))
        self.assertNotIn('해외',row['regions'])
        row=reclassify_article(dict(title='[부산대학소식] 영산대 일본 대학과 협약',body=''))
        self.assertNotIn('부산대학교',row['school_names'])
        row=reclassify_article(dict(title='영남대, 대구 암 환자 서울 원정 줄인다',body=''))
        self.assertNotIn('서울',row['regions'])
        row=reclassify_article(dict(title='인하공전 인천 대학연합 창업경진대회 수상',body=''))
        self.assertEqual(row['school_names'],['인하공업전문대학'])
        row=reclassify_article(dict(title='인천대 학생 연구성과',body=''))
        self.assertEqual(row['school_names'],['인천대학교'])

    def test_education_events_are_not_biographical_degrees(self):
        row=reclassify_article(dict(title='평생교육 행사 소식',body='한신대 평생교육원은 경기캠퍼스에서 수료식을 개최했다.'))
        self.assertEqual(row['school'],'한신대학교')
        self.assertEqual(row['regions'],['경기도'])
        self.assertEqual(row['background_universities'],[])

    def test_official_newsroom_identifies_publishing_university(self):
        row=reclassify_article(dict(title='인공지능데이터사이언스학과, 2026-2 연구실 인턴십 및 학회 성료',
                                    body='구글 뉴스에서 수집한 기사입니다.',source='세종대학교 뉴스룸'))
        self.assertEqual(row['school'],'세종대학교')
        self.assertEqual(row['regions'],['서울'])
        self.assertEqual(row['universities'][0]['identification_method'],'official_newsroom')
        row=reclassify_article(dict(title='학생경력개발처 특강 진행',body='',source='인천대학교 뉴스룸'))
        self.assertEqual(row['school'],'인천대학교')
        row=reclassify_article(dict(title='숭실대 연구성과 발표',body='',source='세종대학교 뉴스룸'))
        self.assertEqual(row['school'],'숭실대학교')
        row=reclassify_article(dict(title='학과 특강 진행',body='',source='일반 언론사'))
        self.assertEqual(row['school'],'대학명 미확인')
        row=reclassify_article(dict(title='교내뉴스> 학생 교육 프로그램 운영',body='',source='한국항공대학교'))
        self.assertEqual(row['school'],'한국항공대학교')

    def test_summary_campus_is_kept_when_title_omits_it(self):
        row=reclassify_article(dict(title='한양대 자랑스러운 공대인 시상',body='서울캠퍼스에서 시상식을 개최했다.'))
        self.assertEqual(row['regions'],['서울'])
        self.assertEqual(row['universities'][0]['campus_status'],'matched')

    def test_campus_region_without_inventing_street_address(self):
        row=reclassify_article(dict(title='한동대 울릉캠퍼스 교육',body=''))
        self.assertEqual(row['regions'],['경북'])
        self.assertEqual(row['universities'][0]['campus_status'],'region_only')
        self.assertEqual(row['universities'][0]['addresses'],[])
        self.assertEqual(row['universities'][0]['campuses'][0]['address'],'')
        self.assertEqual(reclassify_article(dict(title='강원대 삼척캠퍼스 소식',body=''))['regions'],['강원'])

    def test_descriptive_campus_words_do_not_erase_university_region(self):
        for title,region in [('삼육대 미래 캠퍼스 비전 발표','서울'),('재능대 직무 캠퍼스 리크루팅','인천'),
                             ('한국교원대학교 미래 교사들의 캠퍼스 생활','충북'),
                             ('서울대 다소비 캠퍼스 탈탄소 계획','서울')]:
            self.assertIn(region,reclassify_article(dict(title=title,body=''))['regions'],title)
        for title,region in [('인천대 새로운 캠퍼스 독서문화','인천'),('세종대 학생 의견 듣고 캠퍼스 개선','서울'),
                             ('삼육대 지하캠퍼스 비전 발표','서울'),('호서대 가을 캠퍼스 축제','충남')]:
            self.assertIn(region,reclassify_article(dict(title=title,body=''))['regions'],title)
        row=reclassify_article(dict(title='부산대 양산캠퍼스 유휴부지 활용',body=''))
        self.assertEqual(row['regions'],['경남'])
        row=reclassify_article(dict(title='전북대 남원글로컬캠퍼스 교육',body=''))
        self.assertEqual(row['regions'],['전북'])

    def test_verified_campus_variants(self):
        for title,region in [('동국대 와이즈캠퍼스 연구','경북'),('한국외대 글로벌캠퍼스 행사','경기도'),
                             ('건양대 메디컬캠퍼스 행사','대전'),('우석대 진천캠퍼스 지원','충북'),
                             ('경기대 수원캠퍼스 배치도','경기도')]:
            self.assertEqual(reclassify_article(dict(title=title,body=''))['regions'],[region],title)

    def test_compound_region_organizations_and_policies(self):
        for title,expected in [
            ('서울문화재단 청년예술가 지원, 12개 대학 선정',['서울']),
            ('경기창작캠퍼스 전시공간 공모',['경기도']),
            ('충남문화관광재단 창작캠퍼스 행사',['충남']),
            ('인천TP 대학 청년 창업펀드 지원',['인천']),
            ('인천글로벌캠퍼스 산학협력 성과',['인천']),
            ('대전평생교육진흥원 시민대학 강사 모집',['대전']),
            ('제주도민대학 온 페스타',['제주']),
            ('경기도경제과학진흥원 22개 대학 참여',['경기도']),
            ('부산시의회 대학·지역상권 논의',['부산']),
            ('부산서 대학 관계자 총회 개최',['부산']),
            ('충남형 대학정책 성과 발표',['충남']),
            ('강원권 대학 창업 협력',['강원']),
            ('경기 22개 대학 미래기술 성과',['경기도']),
            ('대구경북 15개 대학 청년 축제',['경북','대구'])]:
            self.assertEqual(reclassify_article(dict(title=title,body=''))['regions'],expected,title)
        row=reclassify_article(dict(title='미국 대학 미식축구 경기 직후 총격',body=''))
        self.assertNotIn('경기도',row['regions'])
        for title,region in [('대전특수교육원, 대학 진로체험','대전'),('세종교육문화원 대학 협력','세종'),
                             ('대구어린이세상, 대학과 교육 협력','대구'),('폴리텍Ⅳ대 대전캠퍼스 행사','대전'),
                             ('울산대 현장형 캠퍼스 구축','울산'),('인서울 대학 장학금 논의','서울')]:
            self.assertIn(region,reclassify_article(dict(title=title,body=''))['regions'],title)
        row=reclassify_article(dict(title='대학 축구 경기 22개 대학 참가',body=''))
        self.assertNotIn('경기도',row['regions'])

    def test_education_university_short_names(self):
        for title,region in [('춘천교대, 교육·교원대 양성 플랫폼 운영','강원'),
                             ('서울교대 교수 연구','서울'),('부산교대 학생 지원','부산'),
                             ('청주교대 행사','충북'),('공주교대 협약','충남'),('전주교대 특강','전북')]:
            self.assertEqual(reclassify_article(dict(title=title,body=''))['regions'],[region],title)

    def test_polytechnic_campus_abbreviation_variants(self):
        for prefix in ['한국폴리텍대','한국폴리텍대학','폴리텍대','폴리텍대학','한국폴리텍']:
            title=f'{prefix} 대전캠퍼스, 졸업생 초청 IT 취업 특강'
            row=reclassify_article(dict(title=title,body=''))
            self.assertEqual(row['regions'],['대전'],title)
            self.assertIn('우암로 352-21',row['universities'][0]['addresses'][0])
        self.assertEqual(reclassify_article(dict(title='성남폴리텍대 취업 행사',body=''))['regions'],['경기도'])

    def test_unseen_municipal_education_uses_common_directory(self):
        for title,region in [('청양군, 농업인대학 수료식 개최','충남'),
                             ('함양군, 노인대학 졸업식 열려','경남'),
                             ('정선농업대학 학생 모집','강원'),
                             ('예산농업대학 졸업식','충남'),
                             ('영등포구, 시민대학 수료식','서울')]:
            row=reclassify_article(dict(title=title,body=''))
            self.assertEqual(row['regions'],[region],title)
            self.assertTrue(row['education_programs'])

    def test_ambiguous_municipalities_require_context(self):
        self.assertEqual(reclassify_article(dict(title='고성군, 농업인대학 개강',body=''))['regions'],[])
        self.assertEqual(reclassify_article(dict(title='강원 고성군, 농업인대학 개강',body=''))['regions'],['강원'])
        self.assertEqual(reclassify_article(dict(title='강서구, 시민대학 개강',body=''))['regions'],[])
        self.assertEqual(reclassify_article(dict(title='부산 강서구, 시민대학 개강',body=''))['regions'],['부산'])

    def test_general_venue_and_participant_roles(self):
        row=reclassify_article(dict(title='전북대 연구 행사',body='강릉시에서 포럼이 개최된다.'))
        self.assertEqual(row['regions'],['강원','전북'])
        row=reclassify_article(dict(title='전북대 연구 행사',body='강릉시에서 온 참가자를 대상으로 포럼을 개최했다.'))
        self.assertEqual(row['regions'],['전북'])

    def test_new_feed_sources_use_same_classification(self):
        raw='''<rss><channel><item><title>함양군, 농업인대학 개강</title><link>https://example.com/article</link></item></channel></rss>'''.encode()
        first=parse_feed(raw,'기존 언론사')[0]
        second=parse_feed(raw,'새로 추가한 임의 RSS')[0]
        self.assertEqual(first['regions'],['경남'])
        self.assertEqual(first['regions'],second['regions'])
        self.assertEqual(first['classification_version'],4)

    def test_appointment_excludes_alma_mater_location(self):
        row=reclassify_article(dict(title='신형걸 박사, 존스홉킨스 의대 조교수 임용…신경질환 정밀의학 연구 집중',
            body='신형걸 박사가 미국 존스홉킨스대 의과대학 조교수로 임용됐다. 신 박사는 서울대 전기정보공학부에서 학사와 박사 학위를 받았다. 2016년 서울대를 졸업했다.'))
        self.assertEqual(row['regions'],['해외'])
        self.assertEqual(row['school'],'존스홉킨스대학교')
        self.assertEqual(row['universities'],[])
        self.assertTrue(row['background_universities'])

    def test_domestic_appointment_and_alma_mater(self):
        row=reclassify_article(dict(title='부산대 신임 교수 임용',body='김 교수는 서울대에서 학사 학위를 받았다. 부산대 연구실에서 신기술을 연구한다.'))
        self.assertNotIn('서울',row['regions'])
        self.assertNotIn('서울대학교',row['school'])
        self.assertIn('부산',row['regions'])
        row=reclassify_article(dict(title='숭실대와 서울대 공동연구 협약',body='두 대학은 공동 연구를 추진한다.'))
        self.assertEqual(len(row['universities']),2)

    def test_reported_local_education_and_foreign_visit(self):
        for title,expected in [
            ('음성농업대학, 전문농업경영인 46명 배출',['충북']),
            ('의령군, 제18기 농업인대학 졸업식 열려',['경남']),
            ('봉화군, 호치민 국립경제대학교 글로벌 포럼 참석...K-베트남 밸리 발전 구상 공유',['경북','해외'])]:
            row=reclassify_article(dict(title=title,body=''))
            self.assertEqual(row['regions'],expected,title)
        row=reclassify_article(dict(title='음성농업대학 수료식',body=''))
        self.assertEqual(row['school'],'음성농업대학')
        self.assertEqual(row['universities'],[])
        self.assertEqual(row['education_programs'][0]['kind'],'지자체 운영 교육과정')

    def test_local_participant_not_used_as_organizer(self):
        row=reclassify_article(dict(title='봉화군 출신 청년, 대학 입학',body=''))
        self.assertEqual(row['regions'],[])

    def test_new_abbreviations_and_spacing(self):
        for title,region in [('국립부경대 연구 성과','부산'),('부산과기대 워크숍','부산'),
                             ('차 의과학대학교와 협업','경기도'),('차의과대학 교수 수상','경기도'),
                             ('숭실 대학교 행사','서울'),('폴리텍대학 성남캠퍼스 견학','경기도'),
                             ('춘천폴리텍 장학금 수여','강원')]:
            self.assertEqual(reclassify_article(dict(title=title,body=''))['regions'],[region],title)

    def test_known_campus_and_descriptive_campus(self):
        for title,region in [('상명대 천안캠퍼스 행사','충남'),('인천대 송도캠퍼스 개소','인천'),
                             ('국립경국대 고령친화 캠퍼스센터 개소','경북')]:
            self.assertEqual(reclassify_article(dict(title=title,body=''))['regions'],[region],title)
        row=reclassify_article(dict(title='인제대 현장캠퍼스 시민 개방',body=''))
        self.assertTrue(row['regions'])
        self.assertNotEqual(row['universities'][0]['campus_status'],'unresolved')

    def test_google_news_preserves_publisher_and_date(self):
        raw = '''<rss><channel><item><title>숭실대 연구 성과 - 테스트신문</title>
        <source url="https://example.com">테스트신문</source>
        <link>https://news.google.com/rss/articles/test</link>
        <description>&lt;a&gt;숭실대 연구 성과&lt;/a&gt; 테스트신문</description>
        <pubDate>Tue, 27 Oct 2026 07:25:00 GMT</pubDate></item></channel></rss>'''.encode()
        row = parse_feed(raw, '구글 뉴스')[0]
        self.assertEqual(row['source'], '테스트신문')
        self.assertEqual(row['title'], '숭실대 연구 성과')
        self.assertEqual(row['regions'], ['서울'])
        self.assertEqual(row['date'], '2026-10-27T07:25:00+00:00')
        self.assertTrue(row['via_google'])

    def test_screenshot_university_names(self):
        for title, region in [('숭실대 AI 정책', '서울'), ('경남대 협약', '경남'),
                              ('선문대학교 아산캠퍼스 행사', '충남'), ('서경대 취업 지원', '서울')]:
            self.assertEqual(reclassify_article(dict(title=title, body=''))['regions'], [region])

    def test_address_directory_and_college_abbreviations(self):
        for title, region in [('안산대 학생 지원', '경기도'), ('우송정보대학 행사', '대전'),
                              ('서일대 특강', '서울'), ('삼육보건대 협약', '서울'),
                              ('협성대학교 운영', '경기도')]:
            row = reclassify_article(dict(title=title, body=''))
            self.assertEqual(row['regions'], [region])
            self.assertEqual(row['universities'][0]['method'], 'address_directory')
            self.assertTrue(row['universities'][0]['addresses'])
            self.assertIn('data.go.kr', row['universities'][0]['source'])

    def test_general_or_foreign_article_not_assigned_from_place_word(self):
        for title in ['대학 등록금 정책']:
            self.assertEqual(reclassify_article(dict(title=title, body=''))['regions'], [])

    def test_foreign_news_and_domestic_collaboration(self):
        for title in ['영국 엑시터대학교 장학금 안내', '美대학 축제 소식', '하버드대 연구 성과', '해외 대학 유학 설명회']:
            self.assertEqual(reclassify_article(dict(title=title,body=''))['regions'], ['해외'])
        row = reclassify_article(dict(title='숭실대, 일본 대학과 협약',body=''))
        self.assertEqual(row['regions'], ['서울', '해외'])
        row = reclassify_article(dict(title='대학 교류 행사',body='베트남 현지 대학과 협약했다.'))
        self.assertEqual(row['regions'], ['해외'])
        row = reclassify_article(dict(title='대학 일본어·중국어 강좌 개설',body=''))
        self.assertEqual(row['regions'], [])

    def test_domestic_news_does_not_become_overseas_from_background(self):
        row = reclassify_article(dict(title='AI 활용 금지 대신 책임 선택한 숭실대',
            body='최근 미국과 유럽의 일부 대규모 연구중심대학은 AI 사용을 금지한다. 국내 대학은 다른 방식을 취한다.'))
        self.assertEqual(row['regions'], ['서울'])
        row = reclassify_article(dict(title='숭실대, 하버드대 사례 참고해 교육 개편',body=''))
        self.assertEqual(row['regions'], ['서울'])
        row = reclassify_article(dict(title='숭실대 AI 정책 발표', body='미국 하버드대의 교육 현황을 소개했다.'))
        self.assertEqual(row['regions'], ['서울'])

    def test_real_international_activity_still_overseas(self):
        row = reclassify_article(dict(title='숭실대 국제 공동연구 협약',body='일본 현지 대학과 공동연구 협약을 체결했다.'))
        self.assertEqual(row['regions'], ['서울','해외'])
        row = reclassify_article(dict(title='미국 대학 입학 제도 개편',body=''))
        self.assertEqual(row['regions'], ['해외'])

    def test_participant_hometown_is_not_article_location(self):
        row=reclassify_article(dict(title="전북대 동남아연구소, 아세안 유학생 대상 참가자 모집",
            body='전북대 동남아연구소가 전북특별자치도와 함께 포럼을 개최한다. 포럼은 전주에서 열린다. 서울에서도 아세안 청년 30여 명이 참여한다.'))
        self.assertEqual(row['regions'], ['전북'])
        self.assertFalse(any(p['region']=='서울' for p in row['mentioned_regions']))
        row=reclassify_article(dict(title='전북대 청년 모집',body='부산 출신 참가자와 경기도에 거주하는 청년도 참여한다.'))
        self.assertEqual(row['regions'], ['전북'])

    def test_actual_offsite_venue_is_retained(self):
        row=reclassify_article(dict(title='전북대 연구 포럼 개최',body='포럼은 서울에서 개최된다.'))
        self.assertEqual(row['regions'], ['서울','전북'])
        row=reclassify_article(dict(title='전북대 연구 정책 발표',body='서울의 교육 사례도 함께 비교했다.'))
        self.assertEqual(row['regions'], ['전북'])

    def test_explicit_article_region_without_university(self):
        for title, region in [("'경기도 지산학 미래성장페어' 개막…도내 22개 대학 참여", '경기도'),
                              ('충남도 대학정책 성과 발표', '충남'),
                              ('서울시, 대학과 협약 체결', '서울')]:
            row = reclassify_article(dict(title=title, body=''))
            self.assertEqual(row['regions'], [region])
            self.assertEqual(row['mentioned_regions'][0]['method'], 'title_region')

    def test_explicit_and_university_regions_combined(self):
        row = reclassify_article(dict(title='경기도, 숭실대와 대학 정책 협약', body=''))
        self.assertEqual(row['regions'], ['경기도', '서울'])
        row = reclassify_article(dict(title='서울시립대 연구 성과', body=''))
        self.assertEqual(row['mentioned_regions'], [])

    def test_all_provinces_and_summary_regions(self):
        names = [('서울특별시','서울'),('부산','부산'),('대구광역시','대구'),('인천','인천'),
                 ('광주','광주'),('대전','대전'),('울산','울산'),('세종','세종'),('경기도','경기도'),
                 ('강원','강원'),('충청북도','충북'),('충남','충남'),('전북특별자치도','전북'),
                 ('전남','전남'),('경상북도','경북'),('경남','경남'),('제주','제주')]
        for text, region in names:
            self.assertEqual(reclassify_article(dict(title=f'{text}, 대학 지원 확대',body=''))['regions'], [region])
        row = reclassify_article(dict(title='대학 정책 발표', body='부산광역시에서 대학과 협약했다.'))
        self.assertEqual(row['regions'], ['부산'])
        self.assertEqual(row['mentioned_regions'][0]['method'], 'summary_region')

    def test_ambiguous_place_words(self):
        for title in ['대학 축구 경기 결과 발표', '대학 경기 침체 대응', '경기도 광주시 대학 지원']:
            regions = reclassify_article(dict(title=title, body=''))['regions']
            self.assertEqual(regions, ['경기도'] if '광주시' in title else [])
        self.assertEqual(reclassify_article(dict(title='경기 북부 대학 협력',body=''))['regions'], ['경기도'])
        self.assertEqual(reclassify_article(dict(title='서울·부산 대학 협약',body=''))['regions'], ['부산','서울'])

    def test_similar_names_and_multiple_universities(self):
        self.assertEqual(match_universities('남서울대 연구'), [('남서울대학교', ['충남'])])
        self.assertEqual(len(match_universities('서울대학교와 숭실대학교 협약')), 2)
        self.assertEqual(match_universities('대학 등록금 정책'), [])

    def test_campus_and_unqualified_repeat(self):
        self.assertEqual(reclassify_article(dict(title='한양대 ERICA 연구', body='한양대가 발표'))['regions'], ['경기도'])
        self.assertEqual(reclassify_article(dict(title='연세대(미래) 입학 설명회', body=''))['regions'], ['강원'])
        self.assertEqual(reclassify_article(dict(title='명지대 협약', body=''))['regions'], ['경기도', '서울'])

    def test_campus_addresses_in_same_province_are_distinct(self):
        asan = reclassify_article(dict(title='선문대 아산캠퍼스 행사', body=''))
        cheonan = reclassify_article(dict(title='선문대학교 천안 캠퍼스 행사', body=''))
        for item in (asan, cheonan):
            self.assertEqual(item['regions'], ['충남'])
            self.assertEqual(len(item['universities'][0]['addresses']), 1)
            self.assertEqual(item['universities'][0]['campus_status'], 'matched')
        self.assertIn('아산시', asan['universities'][0]['addresses'][0])
        self.assertIn('천안시', cheonan['universities'][0]['addresses'][0])

    def test_medical_global_and_international_campus_addresses(self):
        for title, road, region in [('경동대 메디컬캠퍼스 연구', '견훤로 815', '강원'),
                                    ('경동대 글로벌캠퍼스 행사', '봉포4길 46', '강원'),
                                    ('연세대 국제캠퍼스 행사', '송도과학로 85', '인천'),
                                    ('ERICA 한양대학교 연구', '한양대학로 55', '경기도')]:
            item = reclassify_article(dict(title=title, body=''))
            self.assertEqual(item['regions'], [region])
            self.assertEqual(len(item['universities'][0]['addresses']), 1)
            self.assertIn(road, item['universities'][0]['addresses'][0])

    def test_unknown_campus_never_receives_headquarters_address(self):
        item = reclassify_article(dict(title='선문대 미등록캠퍼스 행사', body=''))
        self.assertEqual(item['regions'], [])
        self.assertEqual(item['universities'][0]['addresses'], [])
        self.assertEqual(item['universities'][0]['campus_status'], 'unresolved')

    def test_campus_scope_and_summary(self):
        item = reclassify_article(dict(title='한양대 ERICA와 연세대 미래캠퍼스 협약', body=''))
        self.assertEqual(item['universities'][0]['regions'], ['경기도'])
        self.assertEqual(item['universities'][1]['regions'], ['강원'])
        item = reclassify_article(dict(title='선문대학교 행사 개최', body='아산캠퍼스에서 학생들과 만났다.'))
        self.assertIn('아산시', item['universities'][0]['addresses'][0])

    def test_rss_filters_and_normalizes(self):
        raw = '''<rss><channel>
        <item><title>아주대 연구 성과</title><description>&lt;b&gt;새 논문&lt;/b&gt;</description>
        <link>https://example.com/news/1</link><pubDate>Tue, 27 Oct 2026 12:30:00 +0900</pubDate></item>
        <item><title>오늘의 날씨</title><link>https://example.com/weather</link></item>
        <item><title>대학 소식</title><link>javascript:alert(1)</link></item>
        </channel></rss>'''.encode()
        rows = parse_feed(raw, '테스트 RSS')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['regions'], ['경기도'])
        self.assertEqual(rows[0]['body'], '새 논문')
        self.assertEqual(rows[0]['date'], '2026-10-27T03:30:00+00:00')
        self.assertEqual(rows[0]['id'], parse_feed(raw, '테스트 RSS')[0]['id'])

    def test_atom_and_unknown_region(self):
        raw = '''<feed xmlns="http://www.w3.org/2005/Atom"><entry>
        <title>대학 정책 소식</title><link href="https://example.com/policy"/>
        <published>2026-10-26T10:00:00Z</published></entry></feed>'''.encode()
        row = parse_feed(raw, 'Atom')[0]
        self.assertEqual(row['regions'], [])
        self.assertEqual(row['url'], 'https://example.com/policy')
        self.assertTrue(row['date'].endswith('+00:00'))

    def test_bad_dates_do_not_become_current(self):
        for value in ('', 'not a date', '2026-10-27T10:00:00'):
            self.assertEqual(parse_date(value), '')

    def test_source_local_time_uses_explicit_timezone(self):
        self.assertEqual(parse_date('2026-10-27 16:25:11', '+09:00'),
                         '2026-10-27T07:25:11+00:00')
        self.assertEqual(parse_date('2026-10-27 16:25:11'), '')

    def test_html_and_dtd_rejected(self):
        for raw in (b'<html/>', b'<!DOCTYPE rss><rss/>'):
            with self.assertRaises(ValueError):
                parse_feed(raw, 'invalid')


if __name__ == '__main__':
    unittest.main()
