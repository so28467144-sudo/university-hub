from io import BytesIO
import unittest
from zipfile import ZipFile
import xml.etree.ElementTree as ET
from excel_export import make_workbook, article_row
from excel_summary import statistics


class ExcelTests(unittest.TestCase):
    def test_summary_counts_and_chart(self):
        items=[dict(school='가대학교',category='연구·성과'),dict(school='가대학교',category='연구·성과'),
               dict(school='나대학교',category='행사·특강'),dict(school='가대학교 · 나대학교',category='연구·성과')]
        stats=statistics(items)
        self.assertEqual(stats['count'],4)
        self.assertEqual(stats['totals']['연구·성과'],3)
        self.assertEqual(sum(sum(x.values()) for x in stats['schools'].values()),4)
        with ZipFile(BytesIO(make_workbook(items))) as archive:
            for name in archive.namelist(): ET.fromstring(archive.read(name))
            ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            workbook=ET.fromstring(archive.read('xl/workbook.xml'))
            self.assertEqual([s.get('name') for s in workbook.find('s:sheets',ns)],['요약 통계','대학 기사'])
            sheet=ET.fromstring(archive.read('xl/worksheets/sheet2.xml'))
            percentages=[float(c.find('s:v',ns).text) for c in sheet.findall('.//s:c',ns) if c.get('s')=='4']
            self.assertIn(.75,percentages)
            chart=archive.read('xl/charts/chart1.xml').decode()
            self.assertIn('3건 (75.0%)',chart)
            self.assertIn('barDir val="bar"',chart)

    def test_empty_summary(self):
        with ZipFile(BytesIO(make_workbook([]))) as archive:
            for name in archive.namelist(): ET.fromstring(archive.read(name))
            self.assertIn('0건 (0.0%)',archive.read('xl/charts/chart1.xml').decode())

    def test_clickable_url_relationships(self):
        item=dict(title='기사',url='https://example.com/article?a=1&b=2')
        with ZipFile(BytesIO(make_workbook([item]))) as archive:
            sheet=ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
            ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            links=sheet.findall('s:hyperlinks/s:hyperlink',ns)
            self.assertEqual([link.get('ref') for link in links],['F2'])
            rels=ET.fromstring(archive.read('xl/worksheets/_rels/sheet1.xml.rels'))
            self.assertEqual([rel.get('Target') for rel in rels],[item['url']])
            self.assertTrue(all(rel.get('TargetMode')=='External' for rel in rels))
            self.assertEqual(sheet.find('.//s:c[@r="F2"]',ns).get('s'),'1')

    def test_dates_links_and_formula_like_title(self):
        item = dict(school='숭실대학교', date='2026-10-27T07:25:11+00:00', regions=['서울'],
                    title='=SUM(1,2) & <기사>', url='https://news.google.com/rss/articles/test', via_google=True)
        row = article_row(item)
        self.assertEqual(row[1], '2026-10-27 16:25:11')
        self.assertEqual(row[5], item['url'])
        with ZipFile(BytesIO(make_workbook([item]))) as archive:
            for name in archive.namelist():
                ET.fromstring(archive.read(name))
            sheet = ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
            ns = {'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            self.assertEqual(len(sheet.findall('.//s:row',ns)),2)
            cell = sheet.find('.//s:c[@r="E2"]',ns)
            self.assertEqual(cell.get('t'), 'inlineStr')
            self.assertEqual(cell.find('.//s:t',ns).text, item['title'])

    def test_export_order_and_direct_link(self):
        first=dict(title='먼저',url='https://example.com/1')
        second=dict(title='다음',url='https://example.com/2')
        self.assertEqual(article_row(first)[5], first['url'])
        with ZipFile(BytesIO(make_workbook([first,second]))) as archive:
            raw=archive.read('xl/worksheets/sheet1.xml').decode()
            self.assertLess(raw.index('먼저'),raw.index('다음'))

    def test_original_url_preferred_and_single_url_column(self):
        from excel_export import HEADERS
        item=dict(original_url='https://example.com/original',url='https://news.google.com/rss/articles/test',via_google=True)
        self.assertEqual(article_row(item)[5],item['original_url'])
        self.assertEqual([header for header in HEADERS if 'URL' in header],['기사 URL'])
        self.assertEqual(len(article_row(item)),len(HEADERS))


if __name__ == '__main__':
    unittest.main()
