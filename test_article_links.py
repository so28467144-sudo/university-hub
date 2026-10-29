import unittest
from article_links import find_article_url,SEJONG_BOARD

class ArticleLinkTests(unittest.TestCase):
    def test_exact_title_and_detail_id_required(self):
        title='학과, 연구실 인턴십 성료'
        html='<a href="?mode=view&amp;articleNo=895329" title="학과, 연구실 인턴십 성료 자세히 보기">기사</a>'
        self.assertEqual(find_article_url(title,html),SEJONG_BOARD+'?mode=view&articleNo=895329')
        self.assertEqual(find_article_url('다른 기사',html),'')
        self.assertEqual(find_article_url(title,html.replace('?mode=view&amp;articleNo=895329','/')),'')
        self.assertEqual(find_article_url(title,html.replace('?mode=view&amp;articleNo=895329','https://example.com/?mode=view&amp;articleNo=895329')),'')
