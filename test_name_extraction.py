"""지역 저장 결과와 독립적인 대학명 추출 회귀 검증."""
import unittest
from university_regions import extract_article_universities, resolve_universities


class NameExtractionTests(unittest.TestCase):
    def names(self, title, summary=''):
        return [u['name'] for u in extract_article_universities(title, summary)['subjects']]

    def test_korean_variants_and_particles(self):
        for value in ['순천향대학교는', '순천향대가', '순 천 향 대 학 교',
                      '(순천향)대학교는', '순천향(대학교)의', '순천향·대학교',
                      '순천향-대학교', '순천향\u200b대학교', '【순천향대학교】']:
            with self.subTest(value=value):
                self.assertEqual(self.names(value+' 공동 연구 발표'), ['순천향대학교'])

    def test_english_and_previous_names(self):
        for value,name in [('Soonchunhyang University','순천향대학교'),
                           ('soonchunhyang university','순천향대학교'),
                           ('한국산업기술대학교','한국공학대학교'),
                           ('켄텍','한국에너지공과대학교'),
                           ('충북보과대','충북보건과학대학교')]:
            with self.subTest(value=value):
                self.assertEqual(self.names(value+' 연구 발표'), [name])

    def test_summary_and_multiple_subjects(self):
        self.assertEqual(set(self.names('공동 연구 협약', '순천향대와 선문대학교가 공동 연구한다.')),
                         {'순천향대학교','선문대학교'})

    def test_background_is_separate(self):
        result=extract_article_universities('선문대, 연구자 영입', '순천향대학교를 졸업한 김 박사를 영입했다.')
        self.assertEqual([u['name'] for u in result['subjects']], ['선문대학교'])
        self.assertIn('순천향대학교',result['mentions'])
        self.assertIn('순천향대학교',[u['name'] for u in result['background']])

    def test_title_background_and_visiting_guest(self):
        result=extract_article_universities('순천향대 출신 김 박사, 선문대 연구팀 합류')
        self.assertEqual([u['name'] for u in result['subjects']], ['선문대학교'])
        result=extract_article_universities('선문대, 행사 개최', '순천향대 김 교수가 축사를 위해 참석했다.')
        self.assertEqual([u['name'] for u in result['subjects']], ['선문대학교'])

    def test_longest_name_and_ambiguous_aliases(self):
        self.assertEqual(self.names('남서울대학교, 연구 발표'), ['남서울대학교'])
        for value in ['외대 연구 발표','서울대공원 행사','GISTology 연구소', '서울·대구 행사']:
            with self.subTest(value=value):self.assertEqual(self.names(value), [])

    def test_hospital_rule_preserved(self):
        result=extract_article_universities('분당서울대병원, 연구 성과 발표')
        self.assertEqual(result['subjects'],[dict(name='서울대학교',affiliation_type='university_hospital')])
        self.assertEqual(resolve_universities('분당서울대병원 연구')[0]['regions'], ['경기도'])

    def test_no_mutation_and_no_region_result(self):
        title='순천향(대학교) 연구';summary='선문대학교와 공동 연구'
        result=extract_article_universities(title,summary)
        self.assertEqual(title,'순천향(대학교) 연구')
        self.assertNotIn('regions',result)


if __name__=='__main__':unittest.main()
