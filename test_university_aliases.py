import unittest
from university_aliases import generate_aliases
from university_regions import ALIASES,ALIAS_CANDIDATES,REGISTRY,match_universities,reclassify_article


class UniversityAliasTests(unittest.TestCase):
    def test_formal_display_names_and_search_metadata(self):
        row=reclassify_article(dict(title='한기대 연구 소식',body=''))
        self.assertEqual(row['school'],'한국기술교육대학교')
        self.assertIn('한국기술교육대학교',row['school_names'])
        self.assertIn('한기대',row['school_aliases'])
        row=reclassify_article(dict(title='서울문화재단 청년예술가 지원, 12개 대학 선정',body=''))
        self.assertEqual(row['school'],'대학명 미확인')
        self.assertEqual(row['school_names'],[])
        self.assertEqual(row['school_aliases'],[])
    def test_entire_registry_has_formal_and_short_aliases(self):
        for name in REGISTRY:
            for alias in generate_aliases(name):
                key=''.join(alias.lower().split())
                self.assertIn(name,ALIAS_CANDIDATES[key],alias)
        # 주소록 전체의 고유 약칭은 원래 대학으로 되돌아가야 합니다.
        for alias,name in ALIASES.items():
            matches=match_universities(alias+', 연구 소식')
            self.assertIn(name,{n for n,_ in matches},alias)

    def test_additional_abbreviation_types(self):
        examples=[('한기대','충남'),('한체대','서울'),('한국체대','서울'),
                  ('서울예대','경기도'),('부산외대','부산'),('경인교대','인천'),
                  ('명지전문대','서울'),('한경대','경기도'),('한예종','서울'),
                  ('GIST','광주'),('지스트','광주'),('DGIST','대구'),('디지스트','대구'),('유니스트','울산')]
        for alias,region in examples:
            row=reclassify_article(dict(title=alias+', 연구 소식',body=''))
            self.assertIn(region,row['regions'],alias)

    def test_ambiguous_short_alias_not_forced(self):
        self.assertGreater(len(ALIAS_CANDIDATES['외대']),1)
        self.assertEqual(match_universities('외대 연구 소식'),[])
        self.assertEqual(match_universities('부산 외대 연구 소식')[0][0],'부산외국어대학교')
        self.assertEqual(match_universities('한국외국어대학교 발표. 외대의 연구 결과'),[('한국외국어대학교',sorted(REGISTRY['한국외국어대학교']))])
        self.assertEqual(match_universities('서울 교대역 근처 행사'),[])
        self.assertEqual(match_universities('서울대공원 행사'),[])


if __name__=='__main__':unittest.main()
