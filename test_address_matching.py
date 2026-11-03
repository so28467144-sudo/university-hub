import unittest
from university_regions import reclassify_article
from region_diagnostics import diagnose_article


def article(title, body=''):
    return reclassify_article(dict(id='a',title=title,body=body,url='https://example.com'))


class AddressMatchingTests(unittest.TestCase):
    def test_generic_campus_word_does_not_erase_address(self):
        row=article('인천대학교, 문일여고 360명 초청해 캠퍼스 탐방 운영')
        self.assertEqual(row['regions'],['인천'])
        self.assertTrue(row['universities'][0]['address_directory_match'])

    def test_campus_overrides_multiple_locations(self):
        self.assertEqual(article('한양대 ERICA 연구 발표')['regions'],['경기도'])
        self.assertEqual(article('한양대 연구 발표')['regions'],['경기도','서울'])
        self.assertEqual(article('경기도 한양대 연구 발표')['regions'],['경기도'])

    def test_conflict_is_reviewed_even_with_verified_campus(self):
        row=article('서울, 한양대 ERICA 연구 행사')
        self.assertEqual(row['regions'],['경기도'])
        self.assertTrue(row['conflicting_region_evidence'])
        self.assertIn('대학 소재지와 기사 지역 불일치',diagnose_article(row)['review_reasons'])

    def test_subjects_and_background(self):
        row=article('순천향대 연구 발표','서울대 출신 김 박사가 연구했다.')
        self.assertEqual(row['regions'],['충남'])
        row=article('숭실대·순천향대 공동 연구 발표')
        self.assertEqual(set(row['regions']),{'서울','충남'})

    def test_missing_and_unknown_address(self):
        row=article('한국폴리텍대학 장학금 기탁')
        self.assertIn('한국폴리텍대학',row['address_missing_names'])
        self.assertEqual((row['regions'],row['classification_method']),(['전국'],'national_scope'))
        self.assertIn('새봄대학교',diagnose_article(article('새봄대학교 연구 발표'))['additional_confirmation_names'])

    def test_existing_unique_and_hospital_locations(self):
        self.assertEqual(article('순천향대 연구 발표')['regions'],['충남'])
        self.assertEqual(article('분당서울대병원 연구 발표')['regions'],['경기도'])


if __name__=='__main__':unittest.main()
