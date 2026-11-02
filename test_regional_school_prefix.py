import unittest
from university_regions import reclassify_article


class RegionalSchoolPrefixTests(unittest.TestCase):
    def classify(self, title):
        return reclassify_article(dict(id='test', title=title, body='', source='', url='https://example.invalid'))

    def test_verified_concatenated_name(self):
        row = self.classify('부산동명대, 창단 첫 금메달')
        self.assertEqual(row['school_names'], ['동명대학교'])
        self.assertEqual(row['regions'], ['부산'])
        self.assertTrue(row['universities'][0]['addresses'])

    def test_incorrect_prefix_not_inferred(self):
        self.assertNotIn('동명대학교', self.classify('서울동명대 행사')['school_names'])

    def test_multi_region_not_forced(self):
        self.assertEqual(self.classify('서울한양대 협약')['regions'], [])

    def test_longer_school_name_preserved(self):
        self.assertEqual(self.classify('남서울대학교 신입생 모집')['school_names'], ['남서울대학교'])

    def test_university_station_not_school(self):
        self.assertEqual(self.classify('부산동명대역 신설')['school_names'], [])


if __name__ == '__main__': unittest.main()
