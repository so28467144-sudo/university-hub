import unittest
from named_affiliations import FACILITIES,extract_facilities
from university_regions import reclassify_article
from classification_monitor import inspect_article


def classify(title,body=''):
    return reclassify_article(dict(id='test',title=title,body=body))


class AffiliatedInstitutionTests(unittest.TestCase):
    def test_verified_new_institutions(self):
        cases=[('고려대 안산병원','경기도'),('고려대 안암병원','서울'),
               ('중앙대 광명병원','경기도'),('중앙대병원','서울'),('전남대병원','광주'),
               ('한양대병원','서울'),('한양대암병원','서울'),('건양대병원','대전'),
               ('동국대일산병원','경기도'),('동국대 일산한방병원','경기도'),
               ('가톨릭대 인천성모병원','인천'),('가톨릭대 은평성모병원','서울'),
               ('가톨릭대 성빈센트병원','경기도'),('단국대병원','충남')]
        for alias,region in cases:
            with self.subTest(alias=alias):
                row=classify(alias+' 연구 발표')
                self.assertEqual(row['regions'],[region])
                self.assertEqual(row['universities'][0]['affiliation_type'],'university_hospital')
                self.assertTrue(row['universities'][0]['addresses'])
                self.assertEqual(inspect_article(row)[0],[])

    def test_aliases_and_source_records(self):
        self.assertEqual(len({x['name'] for x in FACILITIES}),len(FACILITIES))
        for facility in FACILITIES:
            for alias in facility['aliases']:
                with self.subTest(alias=alias):
                    _,found=extract_facilities(alias+' 연구')
                    self.assertEqual([x['name'] for x in found],[facility['name']])
                    self.assertTrue(found[0]['source'].startswith('https://'))

    def test_branches_do_not_overlap(self):
        for text,name in [('화순전남대병원','화순전남대학교병원'),('한양대구리병원','한양대학교구리병원'),
                          ('중앙대광명병원','중앙대학교광명병원'),('동국대일산한방병원','동국대학교일산한방병원')]:
            self.assertEqual([x['name'] for x in extract_facilities(text)[1]],[name])
        self.assertEqual(extract_facilities('빛고을전남대병원')[1],[])
        self.assertEqual(extract_facilities('충주건국대병원')[1],[])

    def test_unqualified_institution_stays_ambiguous(self):
        for title in ['고려대병원 행사','가톨릭대 성모병원 행사','전남대병원 분원 행사']:
            self.assertEqual(classify(title)['regions'],[])

    def test_parent_mention_does_not_add_campus_candidates(self):
        row=classify('고려대 연구진 발표','고려대 안산병원이 연구했다.')
        self.assertEqual(row['regions'],['경기도'])
        row=classify('고려대 안암병원·고려대 안산병원 공동 연구')
        self.assertEqual(set(row['regions']),{'서울','경기도'})
        self.assertEqual(len(row['universities'][0]['addresses']),2)

    def test_regular_campus_classification_is_unchanged(self):
        self.assertEqual(classify('고려대 세종캠퍼스 연구')['regions'],['세종'])
        self.assertEqual(classify('고려대 연구')['regions'],['서울'])
        self.assertEqual(classify('한양대 ERICA 연구')['regions'],['경기도'])


if __name__=='__main__':unittest.main()
