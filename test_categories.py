import unittest
from article_categories import classify_category

class CategoryTests(unittest.TestCase):
    def test_admissions_are_not_substrings_of_place_names(self):
        self.assertEqual(classify_category('숭실대입구역 청년 창업거리 조성'),'대학 소식')
        self.assertEqual(classify_category('제주 행정시 대학 협력'),'대학 소식')
        self.assertEqual(classify_category('대학 포럼 참가자 모집'),'행사·특강')
        for title in ('대학 2027 수시모집','2027학년도 정시 전형 안내','대입 설명회','신입생 모집'):
            self.assertEqual(classify_category(title),'입시·모집')

    def test_headline_takes_priority_over_summary_topics(self):
        self.assertEqual(classify_category('학생 취업 특강 개최','연구성과와 논문을 소개했다.'),'행사·특강')
        self.assertEqual(classify_category('신기술 논문 발표','후속 행사도 개최한다.'),'연구·성과')
