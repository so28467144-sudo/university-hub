import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from article_dedup import deduplicate, same_story, public_story_groups
from university_regions import reclassify_article
from publication_safety import verified_unknown_fill, publication_errors
from test_publication_safety import mock_run


def row(id,title,school='건양대학교',date='2026-11-02T02:00:00+00:00'):
    return dict(id=id,title=title,school=school,school_names=[school],date=date,body='',
                url='https://example.invalid/'+id,regions=[])


class AdmissionAndCampusRegressionTests(unittest.TestCase):
    def setUp(self):
        self.a=row('a','건양대, 2027학년도 대학원 신입생 모집…국방인재 장학 신설')
        self.b=row('b','건양대, 전기 대학원 신입생 413명 모집…27일까지 접수')

    def test_same_annual_admission_different_numbers_and_publishers(self):
        result=deduplicate([self.a,self.b]);self.assertEqual(len(result),1)
        self.assertEqual(set(result[0]['duplicate_ids']),{'a','b'})

    def test_different_year(self):
        self.b['title']='건양대 2028학년도 전기 대학원 신입생 모집'
        self.assertFalse(same_story(self.a,self.b))

    def test_different_semester(self):
        self.a['title']='건양대 2027학년도 전기 대학원 신입생 모집'
        self.b['title']='건양대 2027학년도 후기 대학원 신입생 모집'
        self.assertFalse(same_story(self.a,self.b))

    def test_different_school(self):
        self.b.update(school='인제대학교',school_names=['인제대학교'])
        self.assertFalse(same_story(self.a,self.b))

    def test_different_graduate_units(self):
        self.a['title']='건양대 2027학년도 교육대학원 신입생 모집'
        self.b['title']='건양대 2027학년도 보건대학원 신입생 모집'
        self.assertFalse(same_story(self.a,self.b))

    def test_different_round_and_quota(self):
        self.a['title']='건양대 2027학년도 전기 대학원 신입생 413명 모집'
        self.b['title']='건양대 2027학년도 전기 대학원 신입생 414명 모집'
        self.assertFalse(same_story(self.a,self.b))
        self.b['title']='건양대 2027학년도 전기 대학원 신입생 추가모집'
        self.assertFalse(same_story(self.a,self.b))

    def test_different_deadline(self):
        self.a['title']='건양대 2027학년도 대학원 신입생 모집 27일까지 접수'
        self.b['title']='건양대 2027학년도 대학원 신입생 모집 30일까지 접수'
        self.assertFalse(same_story(self.a,self.b))

    def test_different_round_or_department(self):
        for a,b in [('건양대 2027학년도 대학원 1차 신입생 모집','건양대 2027학년도 대학원 2차 신입생 모집'),
                    ('건양대 2027학년도 대학원 간호학과 신입생 모집','건양대 2027학년도 대학원 임상병리학과 신입생 모집')]:
            self.assertFalse(same_story(row('a',a),row('b',b)))

    def test_formatted_amount_is_not_a_different_event(self):
        self.assertTrue(same_story(row('a','건양대 AI·SW 우수 역량 학생 66명에 장학금 3120만원'),
                                   row('b','건양대 AI·SW 우수 역량 학생 66명에 장학금 3,120만원')))

    def test_named_event_extra_details_without_numeric_conflict(self):
        a=row('a','전남대 대학원 연구성과 나누는 2026 용봉학술제 G-Fair 개최','전남대학교')
        b=row('b','전남대 대학원 4~6일 2026 용봉학술제 G-Fair 개최 논문 610건 발표','전남대학교')
        self.assertTrue(same_story(a,b))
        a['title']+=' 논문 620건 발표';self.assertFalse(same_story(a,b))

    def test_different_photo_sequence_and_hospital_stay_separate(self):
        self.assertFalse(same_story(row('a',"[포토] 부산패션위크 동명대학교 컬렉션 LOOK 3",'동명대학교'),row('b',"[포토] 부산패션위크 동명대학교 컬렉션 LOOK 4",'동명대학교')))
        self.assertFalse(same_story(row('a','충남대학교병원 만성폐쇄성폐질환 평가 1등급','충남대학교'),row('b','세종충남대병원 만성폐쇄성폐질환 평가 1등급','충남대학교')))

    def test_same_headline_different_substantive_bodies_not_merged(self):
        a=row('a','건양대 연구성과 발표');b=row('b','건양대 연구성과 발표')
        a['body']='신경세포에서 단백질 작용을 관찰하고 새로운 항암 물질의 세포 반응과 임상시험 결과를 분석했다. '*8
        b['body']='전기자동차 도로 주행 데이터를 활용한 배터리 설계와 풍력발전 장치의 에너지 효율을 실험했다. '*8
        self.assertFalse(same_story(a,b))
        a['title']=b['title']='건양대 2027학년도 대학원 신입생 모집'
        self.assertFalse(same_story(a,b))

    def test_different_date_and_unknown_year_no_semantic_merge(self):
        self.b['date']='2026-11-12T02:00:00+00:00';self.assertFalse(same_story(self.a,self.b))
        self.b['date']='';self.assertFalse(same_story(self.a,self.b))

    def test_explicit_campus_conflict(self):
        self.a['universities']=[dict(name='건양대학교',campus_status='matched',campus_names=['논산캠퍼스'])]
        self.b['universities']=[dict(name='건양대학교',campus_status='matched',campus_names=['메디컬캠퍼스'])]
        self.assertFalse(same_story(self.a,self.b))

    def test_campus_short_forms(self):
        for title,region in [('건양대 메디컬캠 학술대회','대전'),('전남대 여수캠 연구 발표','전남'),('동국대 WISE캠 연구 발표','경북'),('고려대 세종캠 연구 발표','세종')]:
            with self.subTest(title=title):self.assertEqual(reclassify_article(row('x',title))['regions'],[region])

    def test_campus_short_form_false_positive(self):
        self.assertEqual(reclassify_article(row('x','건양대 메디컬캠프 프로그램'))['regions'],['충남'])

    def test_main_campus_and_article_location_priority(self):
        for title,region,method in [('인제대 연구 발표','경남','main_campus_default'),('건양대 대학원 신입생 모집','충남','main_campus_default'),('김해댕댕파크, 인제대 실습 거점으로','경남','main_campus_default')]:
            with self.subTest(title=title):
                result=reclassify_article(row('x',title))
                self.assertEqual((result['regions'],result['classification_method']),([region],method))

    def test_verified_unit_with_punctuation(self):
        for title,region in [('인제대 임상병리학과 학술상 수상','경남'),('인제대, 대학일자리플러스센터 취업교육 개최','경남'),('건양대 의공학과 수상','대전')]:
            with self.subTest(title=title):self.assertEqual(reclassify_article(row('x',title))['regions'],[region])

    def test_company_campus_tour_is_not_university_campus(self):
        self.assertEqual(reclassify_article(row('x','세종대학교 대학일자리센터 한국투자증권 캠퍼스투어'))['regions'],['서울'])

    def test_geographic_unidentified_university_not_a_proper_name(self):
        item=reclassify_article(row('x','용인 대학서 학생 학교버스에 깔려 병원 이송'))
        self.assertNotIn('용인대학교',item['school_names'])
        self.assertEqual(reclassify_article(row('x','용인 대학교 연구 발표'))['school_names'],['용인대학교'])

    def test_other_campus_region_stays_for_review(self):
        result=reclassify_article(row('x','인제대, 부산 기관과 협약'))
        self.assertEqual((result['regions'],result['classification_method']),([],'review_required'))

    def test_former_campus_role_not_current_location(self):
        a=row('a','성균관대 총장 연임')
        a['body']='1994년 성균관대에 부임해 자연과학캠퍼스 부총장 겸 산학협력단장 등을 역임했다.'
        self.assertEqual(reclassify_article(a)['regions'],['서울'])

    def test_column_author_affiliation_is_not_subject_university(self):
        a=row('a','대학 행정에 묻다')
        a['body']='[칼럼_ 홍길동 방송대 교수] 대학의 교육 행정을 둘러싼 일반 정책을 논의한다.'
        self.assertEqual(reclassify_article(a)['regions'],[])

    def test_only_verified_unknown_can_fill(self):
        a=row('a','건양대 메디컬캠 학술대회');b=reclassify_article(a)
        self.assertTrue(verified_unknown_fill(a,b));self.assertEqual(publication_errors([a],[a],[b],[a]),[])
        a['regions']=['충남'];self.assertFalse(verified_unknown_fill(a,b))

    def test_collector_preserves_all_originals_and_emits_groups(self):
        with TemporaryDirectory() as d:
            root=Path(d);original=[self.a,self.b,row('c','인제대, 대학일자리플러스센터 취업교육 개최','인제대학교')]
            (root/'news.json').write_text(json.dumps(dict(news=original,status={})),encoding='utf-8')
            out=mock_run(root)
            self.assertEqual(len(out['news']),3);self.assertEqual(len(out['raw_news']),3)
            self.assertEqual(out['status']['public_story_groups'],[])
            self.assertTrue(any(set(g['article_ids'])=={'a','b'} for g in out['status']['duplicate_review_candidates']))
            self.assertEqual(next(a for a in out['news'] if a['id']=='c')['regions'],['경남'])
            self.assertEqual(next(a for a in out['raw_news'] if a['id']=='c')['regions'],[])
            self.assertTrue(any(r['automatic_change_applied'] for r in out['region_change_reviews']))


if __name__=='__main__':unittest.main()
