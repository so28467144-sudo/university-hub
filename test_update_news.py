import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from contextlib import redirect_stdout
import unittest
import update_news
from university_regions import reclassify_article

class UpdateNewsTests(unittest.TestCase):
    def test_existing_articles_cursor_and_diagnostics_survive_updates(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);path=root/'news.json'
            original=dict(news=[dict(id='old',title='순천향대학교 연구',body='',url='https://example.com/old',date='2026-10-29T01:00:00+00:00')],status={},search_cursor=30,custom='keep')
            path.write_text(json.dumps(original),encoding='utf-8')
            class FakeCollector:
                def __init__(self):
                    self.cache=json.loads((root/'.rss-cache.json').read_text(encoding='utf-8'))
                    self.search_cursor=self.cache['search_cursor']
                def refresh(self):self.search_cursor+=30
                def snapshot(self):return [reclassify_article(n) for n in self.cache['news']],dict(state='ready')
            with patch.object(update_news,'Collector',FakeCollector),redirect_stdout(io.StringIO()):
                output=update_news.update_news(root)
                self.assertEqual(output['search_cursor'],60)
                output=update_news.update_news(root)
                self.assertEqual(output['search_cursor'],90)
            self.assertEqual([n['id'] for n in output['news']],['old'])
            self.assertEqual(output['news'][0]['url'],original['news'][0]['url'])
            self.assertEqual(output['custom'],'keep')
            self.assertEqual(json.loads((root/'classification_diagnostics.json').read_text(encoding='utf-8'))['total'],1)
            self.assertTrue((root/'classification_diagnostics.csv').exists())

    def test_failed_collection_does_not_reset_public_news(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);path=root/'news.json'
            path.write_text(json.dumps(dict(news=[dict(id='old')],status={})),encoding='utf-8')
            before=path.read_bytes()
            with patch.object(update_news,'Collector') as factory:
                factory.return_value.snapshot.return_value=([dict(id='old')],dict(state='error'))
                with self.assertRaises(RuntimeError):update_news.update_news(root)
            self.assertEqual(path.read_bytes(),before)
