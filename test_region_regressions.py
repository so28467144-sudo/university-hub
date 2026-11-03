import unittest
from copy import deepcopy
from university_regions import reclassify_article
from region_diagnostics import diagnose_article
from classification_monitor import inspect_article


def classify(title,body=''):
    return reclassify_article(dict(id='test',title=title,body=body,date='2026-10-29T01:00:00+00:00'))


class RegionRegressionTests(unittest.TestCase):
    def test_partner_location_keeps_verified_school(self):
        row=classify('경북 기관, 부산가톨릭대학교와 창업 협약 체결')
        self.assertEqual(row['regions'],['부산'])
        self.assertTrue(row['conflicting_region_evidence'])
        self.assertEqual(inspect_article(row)[0],[])

    def test_venue_is_not_school_location(self):
        row=classify('전북대 포럼 개최','포럼은 서울에서 개최된다.')
        self.assertEqual(row['regions'],['전북'])
        self.assertIn('event_venue',{p['role'] for p in row['mentioned_regions']})
        row=classify('한양대 포럼 개최','포럼은 서울에서 개최된다.')
        self.assertEqual((row['regions'],row['classification_method']),(['경기도','서울'],'multi_campus_estimate'))

    def test_multiple_school_location_is_scoped(self):
        row=classify('경기도 한양대와 연세대 공동연구')
        schools={u['name']:u['regions'] for u in row['universities']}
        self.assertEqual(schools['한양대학교'],['경기도'])
        self.assertEqual(schools['연세대학교'],['강원','서울','인천'])

    def test_verified_hospitals(self):
        for title,region in [('한양대구리병원 연구 발표','경기도'),('고려대 구로병원 연구 발표','서울'),('건국대병원 연구 발표','서울')]:
            with self.subTest(title=title):
                row=classify(title)
                self.assertEqual(row['regions'],[region])
                self.assertEqual(row['universities'][0]['affiliation_type'],'university_hospital')
        self.assertNotIn('서울',classify('충주건국대병원 연구 발표')['regions'])

    def test_cha_and_general_faculties(self):
        row=classify('차 의대 약학대학, 제약회사와 협약')
        self.assertEqual(row['school_names'],['차의과학대학교'])
        self.assertNotIn('약학대학',diagnose_article(row)['additional_confirmation_names'])
        for name in ['정보대학','단과대학','행정대학원']:
            self.assertEqual(diagnose_article(classify(name+' 행사'))['additional_confirmation_names'],[])

    def test_supplemented_campuses_are_not_assumed(self):
        self.assertEqual(classify('부산가톨릭대 하하캠퍼스 행사')['regions'],['부산'])
        self.assertEqual(classify('성균관대 자연과학캠퍼스 행사')['regions'],['경기도'])
        self.assertEqual(classify('성균관대 연구 발표')['regions'],['경기도','서울'])

    def test_ellipsis_preserves_foreign_context(self):
        self.assertEqual(classify('경제난 중국, 지원금 축소…대학들 허리띠 졸라맨다')['regions'],['해외'])
        self.assertEqual(classify('숭실대 AI 정책 발표','중국 대학의 사례와 비교했다.')['regions'],['서울'])

    def test_monitor_detects_real_corruption(self):
        row=classify('경북 기관, 부산가톨릭대학교와 협약')
        broken=deepcopy(row);broken['regions']=['경북']
        self.assertIn('region_evidence_mismatch',inspect_article(broken)[0])
        row=classify('고려대병원 행사');row['universities'][0]['regions']=['서울'];row['regions']=['서울']
        self.assertIn('ambiguous_campus_assigned_region',inspect_article(row)[0])


if __name__=='__main__':unittest.main()
