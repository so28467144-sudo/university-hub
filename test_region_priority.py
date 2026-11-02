import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from university_regions import reclassify_article
from region_diagnostics import diagnose_article,export_diagnostics,REASONS

def classify(title,body=''):
    return reclassify_article(dict(id='test',title=title,body=body,url='https://example.com/article'))

class RegionPriorityTests(unittest.TestCase):
    def test_formal_short_english_and_parentheses_names(self):
        for text in ('순천향대학교는 연구를 발표했다','순천향대에서 연구 발표','(순천향대) 연구 발표',
                     '순 천 향 대 연구 발표','순천향(대) 연구 발표','Soonchunhyang University announces research',
                     'soonchunhyang univ. 연구 발표','순천향\u200b대학교 연구 발표'):
            row=classify(text)
            self.assertEqual(row['school_names'],['순천향대학교'],text)
            self.assertEqual(row['regions'],['충남'],text)

    def test_verified_aliases_and_former_name(self):
        for text,name,region in [('켄텍 연구성과','한국에너지공과대학교','전남'),
                                 ('충북보과대 특강','충북보건과학대학교','충북'),
                                 ('충북도립대학 연구 발표','충북도립대학교','충북'),
                                 ('한국산업기술대학교 연구 발표','한국공학대학교','경기도')]:
            row=classify(text);self.assertEqual(row['school_names'],[name]);self.assertEqual(row['regions'],[region])

    def test_english_boundary_and_similar_names(self):
        self.assertEqual(classify('POSTECHNOLOGY 소식')['school_names'],[])
        self.assertEqual(classify('남서울대 연구 발표')['school_names'],['남서울대학교'])
        self.assertEqual(classify('동서울대학교 특강')['school_names'],['동서울대학교'])

    def test_campus_and_article_region_priority(self):
        self.assertEqual(classify('한양대 ERICA 연구 발표')['regions'],['경기도'])
        row=classify('한양대 연구 발표')
        self.assertEqual(row['regions'],[])
        self.assertEqual(row['universities'][0]['candidate_regions'],['경기도','서울'])
        row=classify('경기도 한양대 연구 발표')
        self.assertEqual(row['universities'][0]['regions'],['경기도'])
        self.assertEqual(row['universities'][0]['region_resolution'],'article_address_intersection')
        row=classify('한양대 알수없는캠퍼스 연구 발표')
        self.assertEqual(row['regions'],[])
        self.assertEqual(row['universities'][0]['addresses'],[])
        row=classify('조지메이슨대학교 한국캠퍼스 교육기술 수상')
        self.assertEqual(row['regions'],['인천'])
        self.assertEqual(row['universities'][0]['campus_status'],'matched')
        self.assertEqual(classify('산기협, 용인 9개 대학 취업 지원 행사 개최')['regions'],['경기도'])
        self.assertEqual(classify('광주 9개 대학 행사 개최')['regions'],['광주'])  # 시·도가 명시된 기존 규칙

    def test_regional_education_words_are_not_university_aliases(self):
        self.assertNotIn('충남대학교',classify('충남 대학정책 최우수 평가')['school_names'])
        self.assertNotIn('부산대학교',classify('부산대학축구 성과')['school_names'])
        self.assertEqual(classify('동명대 출신 장교들, 모교 찾아 후배 진로 조언')['regions'],['부산'])

    def test_hospital_and_alma_mater_are_separate(self):
        self.assertEqual(classify('분당서울대병원 연구 발표')['regions'],['경기도'])
        row=classify('서울대 출신 김 교수, 부산대 신임 교수 임용')
        self.assertEqual(row['school_names'],['부산대학교'])
        self.assertEqual(row['regions'],['부산'])
        self.assertEqual(diagnose_article(classify('서울대 출신 김 박사, 책 발간'))['failure_reasons'],['학력·출신 대학만 언급'])
        row=classify('삼육대 개교 기념식 개최','광운대 총장이 참석해 축사를 했다.')
        self.assertEqual(row['school_names'],['삼육대학교'])
        row=classify('삼육대 공동연구 협약','광운대 교수와 함께 공동연구를 진행한다.')
        self.assertIn('광운대학교',row['school_names'])

    def test_diagnostics_distinguish_uncertainty(self):
        cases=[('새봄대학교 연구 발표','대학 주소록 미등록'),
               ('외대 연구 발표','대학명 중복 또는 모호함'),
               ('한양대 연구 발표','캠퍼스 특정 불가')]
        for title,reason in cases:self.assertIn(reason,diagnose_article(classify(title))['failure_reasons'])
        row=classify('숭실대·서울대 공동연구 협약')
        self.assertIn('기사에 여러 대학 등장',diagnose_article(row)['review_reasons'])
        self.assertEqual(row['regions'],['서울'])
        row=classify('경기도, 숭실대와 협약')
        self.assertIn('대학 소재지와 기사 지역 불일치',diagnose_article(row)['review_reasons'])

    def test_diagnostics_export_and_idempotence(self):
        items=[classify('순천향대학교 행사'),classify('새봄대학교 발표')]
        for item in items:
            again=reclassify_article(item)
            self.assertEqual(item['regions'],again['regions'])
            self.assertEqual(item['school_names'],again['school_names'])
        with TemporaryDirectory() as directory:
            json_path=Path(directory)/'diagnostics.json';csv_path=Path(directory)/'diagnostics.csv'
            payload=export_diagnostics(items,json_path,csv_path)
            self.assertEqual(payload['total'],2)
            self.assertEqual(json.loads(json_path.read_text(encoding='utf-8'))['unclassified'],1)
            with csv_path.open(encoding='utf-8-sig',newline='') as stream:self.assertEqual(len(list(csv.DictReader(stream))),2)
            self.assertTrue(all(reason in REASONS for row in payload['articles'] for reason in row['failure_reasons']))
