import json
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from test_publication_safety import article, mock_run
from publication_safety import PublicationBlocked
from news_storage import STATE_PATH, load_state, prepare_pair, write_pair, validate_pair


class SplitStorageTests(unittest.TestCase):
    def test_legacy_migration_three_cold_runners(self):
        with TemporaryDirectory() as base:
            current=Path(base)/'0';current.mkdir()
            a=article();a['pending_update']={'body':'new internal body'}
            (current/'news.json').write_text(json.dumps(dict(news=[a],status={},raw_news=[a])),encoding='utf-8')
            for n in range(1,4):
                target=Path(base)/str(n);target.mkdir();shutil.copy2(current/'news.json',target/'news.json')
                if (current/STATE_PATH).exists():
                    (target/STATE_PATH).parent.mkdir();shutil.copy2(current/STATE_PATH,target/STATE_PATH)
                mock_run(target)
                public=json.loads((target/'news.json').read_bytes());state=validate_pair(target)
                self.assertEqual(len(public['news']),1);self.assertNotIn('raw_news',public)
                self.assertNotIn('pending_update',public['news'][0]);self.assertNotIn('region_change_reviews',public)
                self.assertEqual(state['raw_news'][0]['pending_update'],a['pending_update'])
                self.assertEqual(state['raw_news'][0]['body'],a['body']);current=target

    def test_missing_corrupt_and_wrong_generation_block_before_collection(self):
        for mode in ('missing','corrupt','wrong_generation','public_changed'):
            with self.subTest(mode=mode),TemporaryDirectory() as d:
                root=Path(d);(root/'news.json').write_text(json.dumps(dict(news=[article()],status={})),encoding='utf-8');mock_run(root)
                if mode=='missing':(root/STATE_PATH).unlink()
                elif mode=='corrupt':(root/STATE_PATH).write_text('{bad')
                else:
                    pub=json.loads((root/'news.json').read_bytes())
                    if mode=='wrong_generation':pub['preservation']['generation']='wrong'
                    else:pub['status']['tampered']=True
                    (root/'news.json').write_text(json.dumps(pub),encoding='utf-8')
                before=(root/'news.json').read_bytes()
                with patch('update_news.Collector') as collector:
                    with self.assertRaises(PublicationBlocked):mock_run(root)
                    collector.assert_not_called()
                self.assertEqual(before,(root/'news.json').read_bytes())

    def test_second_replace_failure_restores_old_pair(self):
        with TemporaryDirectory() as d:
            root=Path(d);output=dict(news=[article()],raw_news=[article()],status={})
            write_pair(root,*prepare_pair(output));old_public=(root/'news.json').read_bytes();old_state=(root/STATE_PATH).read_bytes()
            original=Path.replace
            def fail(path,target):
                if path.name=='news.publish.tmp':raise OSError('injected public replace failure')
                return original(path,target)
            with patch.object(Path,'replace',fail):
                with self.assertRaises(OSError):write_pair(root,*prepare_pair(output))
            self.assertEqual(old_public,(root/'news.json').read_bytes());self.assertEqual(old_state,(root/STATE_PATH).read_bytes());validate_pair(root)

    def test_interrupted_split_pair_blocks(self):
        with TemporaryDirectory() as d:
            root=Path(d);output=dict(news=[article()],raw_news=[article()],status={})
            write_pair(root,*prepare_pair(output));before=(root/'news.json').read_bytes()
            _,future=prepare_pair(output);(root/STATE_PATH).write_bytes(future)
            with self.assertRaises(ValueError):validate_pair(root)
            self.assertEqual(before,(root/'news.json').read_bytes())

    def test_prepare_write_failure_keeps_pair(self):
        with TemporaryDirectory() as d:
            root=Path(d);output=dict(news=[article()],raw_news=[article()],status={})
            write_pair(root,*prepare_pair(output));before=(root/'news.json').read_bytes();old=(root/STATE_PATH).read_bytes()
            original=Path.write_bytes
            def fail(path,value):
                if path.name=='news-preservation.tmp':raise OSError('injected disk full')
                return original(path,value)
            with patch.object(Path,'write_bytes',fail):
                with self.assertRaises(OSError):write_pair(root,*prepare_pair(output))
            self.assertEqual(before,(root/'news.json').read_bytes());self.assertEqual(old,(root/STATE_PATH).read_bytes())

    def test_orphan_state_cannot_be_used_as_legacy(self):
        with TemporaryDirectory() as d:
            root=Path(d);(root/STATE_PATH).parent.mkdir();(root/STATE_PATH).write_text('{}')
            with self.assertRaises(ValueError):load_state(root,dict(news=[article()],status={}))


if __name__=='__main__':unittest.main()
