import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from region_diagnostics import generate_report,export_diagnostics,REASONS


class DiagnosticReportTests(unittest.TestCase):
    def test_report_preserves_input_and_counts_stored_regions(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);source=root/'news.json'
            source.write_text(json.dumps(dict(news=[
                dict(id='1',title='순천향대 연구 발표',regions=['충남']),
                dict(id='2',title='새봄대학교 연구 발표',regions=[]),
                dict(id='3',title='대학 정책 발표',regions=[])])),encoding='utf-8')
            before=source.read_bytes()
            report=generate_report(source,root/'out')
            self.assertEqual(source.read_bytes(),before)
            self.assertEqual((report['total'],report['classified'],report['unclassified']),(3,1,2))
            self.assertEqual(report['unclassified_percent'],66.67)
            self.assertEqual(len(report['articles']),2)
            self.assertEqual(set(report['failure_reason_counts']),set(REASONS))
            self.assertIn('새봄대학교',[row['name'] for row in report['additional_confirmation_names']])
            self.assertEqual(json.loads((root/'out/review_universities.json').read_text(encoding='utf-8')),report['additional_confirmation_names'])
            data=(root/'out/diagnostics.csv').read_bytes()
            self.assertNotIn(b'\r\r\n',data)
            with (root/'out/diagnostics.csv').open(encoding='utf-8-sig',newline='') as stream:
                self.assertEqual(len(list(csv.DictReader(stream))),2)

    def test_empty_dataset(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            report=export_diagnostics([],root/'j/a.json',root/'c/a.csv',True)
            self.assertEqual(report['unclassified_percent'],0)
            self.assertEqual(report['additional_confirmation_names'],[])

    def test_collision_and_invalid_input_do_not_overwrite(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);source=root/'diagnostics.json'
            source.write_text('{"news":[]}',encoding='utf-8');before=source.read_bytes()
            with self.assertRaises(ValueError):generate_report(source,root)
            self.assertEqual(source.read_bytes(),before)
            source.write_text('<<<<<<< conflict',encoding='utf-8')
            with self.assertRaises(ValueError):generate_report(source,root/'out')
            self.assertFalse((root/'out').exists())


if __name__=='__main__':unittest.main()
