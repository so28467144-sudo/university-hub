import unittest
from university_regions import reclassify_article
from classification_monitor import inspect_article


def classify(title,body=''):
    return reclassify_article(dict(id='test',title=title,body=body))


class CampusIdentityCueTests(unittest.TestCase):
    def test_wise_variants(self):
        for title in ['동국대 WISE 교수 연구','동국대 wise 교수 연구','동국대학교 WISE캠퍼스 연구',
                      '동국대 와이즈캠퍼스 연구','동국대 와이즈 연구','동국대(WISE) 연구']:
            with self.subTest(title=title):
                row=classify(title)
                self.assertEqual(row['regions'],['경북'])
                self.assertEqual(inspect_article(row)[0],[])

    def test_same_alias_does_not_apply_to_other_universities(self):
        self.assertEqual(classify('한양대 WISE 기업과 협약')['regions'],['서울'])
        self.assertEqual(classify('동국대 WISEly 기업과 협약')['regions'],['서울'])
        self.assertEqual(classify('동국대 WISE 기업과 협약')['regions'],['서울'])
        self.assertEqual(classify('동국대 와이즈한 교육 정책')['regions'],['서울'])
        self.assertEqual(classify('동국대 연구 발표','기업 WISE와 협약했다.')['regions'],['서울'])

    def test_verified_department_and_project(self):
        self.assertEqual(classify('안양대 유아교육과 행사')['regions'],['경기도'])
        self.assertEqual(classify('고려대 세종앵커사업단 행사')['regions'],['세종'])
        self.assertEqual(classify('안양대 공동 행사','외부기관 유아교육과와 협약했다.')['classification_method'],'main_campus_default')

    def test_locality_before_school_only(self):
        self.assertEqual(classify('김해 인제대, 연구 발표')['regions'],['경남'])
        self.assertEqual(classify('인제대, 김해 기관과 협약')['classification_method'],'main_campus_default')
        self.assertEqual(classify('인제대 포럼 개최','김해에서 열린다.')['classification_method'],'main_campus_default')

    def test_future_word_requires_admissions_context(self):
        self.assertEqual(classify('연세대 미래 출결 반영')['regions'],['강원'])
        self.assertEqual(classify('연세대 미래 연구 정책')['regions'],['서울'])
        self.assertEqual(classify('연세대 미래산업 연구')['regions'],['서울'])

    def test_multiple_school_evidence_is_scoped(self):
        row=classify('한양대·연세대 미래 출결 10%')
        schools={u['name']:u['regions'] for u in row['universities']}
        self.assertEqual(schools['한양대학교'],[])
        self.assertEqual(schools['연세대학교'],['강원'])
        self.assertTrue(row['universities'][1]['campus_cue_evidence'])


if __name__=='__main__':unittest.main()
