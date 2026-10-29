import unittest
from urllib.parse import urlsplit,parse_qs
from rss_searches import build_search_plan,select_search_batch
from university_regions import REGISTRY


class SearchPlanTests(unittest.TestCase):
    def test_university_coverage_and_query_period(self):
        plan=build_search_plan(dict(enabled=True,lookback_days=30,universities_per_query=5))
        queries=[parse_qs(urlsplit(source['url']).query)['q'][0] for source in plan]
        self.assertTrue(all('when:30d' in query for query in queries))
        eligible=[name for name,regions in REGISTRY.items() if regions and '캠퍼스' not in name and '대학원' not in name and not name.startswith('한국폴리텍')]
        for name in eligible:self.assertTrue(any('"'+name+'"' in query for query in queries),name)
        self.assertEqual(len({s['url'] for s in plan}),len(plan))

    def test_rotation_covers_entire_plan(self):
        plan=build_search_plan(dict(enabled=True))
        seen=set();cursor=0
        for _ in range((len(plan)+29)//30):
            batch,cursor=select_search_batch(plan,cursor,30)
            self.assertLessEqual(len(batch),30)
            seen.update(s['url'] for s in batch)
        self.assertEqual(seen,{s['url'] for s in plan})
        self.assertEqual(build_search_plan(dict(enabled=False)),[])


if __name__=='__main__':unittest.main()
