"""저장 기사 중복·날짜·검색 범위 및 선택한 링크의 읽기 전용 점검."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone,timedelta
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from urllib.request import Request,urlopen
from article_dedup import deduplicate
from rss_searches import build_search_plan
from university_regions import REGISTRY

ROOT=Path(__file__).resolve().parent

class PageTitle(HTMLParser):
    def __init__(self):super().__init__();self.inside=False;self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag=='title':self.inside=True
    def handle_endtag(self,tag):
        if tag=='title':self.inside=False
    def handle_data(self,data):
        if self.inside:self.parts.append(data)

def check_link(item):
    url=item.get('original_url') or item['url']
    result=dict(id=item['id'],title=item['title'],requested_url=url)
    try:
        with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0 CampusOnLinkAudit/1.0'}),timeout=12) as response:
            body=response.read(1_000_000)
            result.update(status=response.status,final_url=response.url)
            page=PageTitle();page.feed(body.decode(response.headers.get_content_charset() or 'utf-8',errors='replace'))
            result['page_title']=' '.join(page.parts).strip()
        result['home_redirect']=urlsplit(result['final_url']).path in ('','/','/index.html','/index.do')
        result['google_interstitial']=urlsplit(result['final_url']).hostname=='news.google.com'
    except Exception as exc:result['error']=f'{type(exc).__name__}: {exc}'
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--links',action='store_true');args=parser.parse_args()
    data=json.loads((ROOT/'.rss-cache.json').read_text(encoding='utf-8'));raw=data['raw_news']
    unique=deduplicate(raw);old_groups={frozenset(n.get('duplicate_ids',[n['id']])) for n in data['news']}
    new_by_id={id:n['id'] for n in unique for id in n['duplicate_ids']}
    split_groups=[]
    for group in old_groups:
        representatives={new_by_id[id] for id in group if id in new_by_id}
        if len(representatives)>1:split_groups.append(dict(original_ids=sorted(group),new_representatives=sorted(representatives)))
    dates=Counter();date_problems=[]
    for n in raw:
        if not n.get('date'):dates['missing']+=1;continue
        try:
            stamp=datetime.fromisoformat(n['date'])
            if stamp.tzinfo is None:dates['naive']+=1;date_problems.append(n['id'])
            elif stamp.astimezone(timezone(timedelta(hours=9))).date()>datetime.now(timezone(timedelta(hours=9))).date():
                dates['future']+=1;date_problems.append(n['id'])
            else:dates['valid']+=1
        except ValueError:dates['invalid']+=1;date_problems.append(n['id'])
    config=json.loads((ROOT/'rss_search_config.json').read_text(encoding='utf-8'))
    plan=build_search_plan(config);queries=[parse_qs(urlsplit(s['url']).query)['q'][0] for s in plan]
    eligible=[name for name,regions in REGISTRY.items() if regions and '캠퍼스' not in name and '대학원' not in name and not name.startswith('한국폴리텍')]
    uncovered=[name for name in eligible if not any('"'+name+'"' in q for q in queries)]
    roots=[n['id'] for n in raw if urlsplit(n.get('original_url') or n['url']).path in ('','/','/index.html','/index.do')]
    result=dict(checked_at=datetime.now(timezone(timedelta(hours=9))).isoformat(),raw_count=len(raw),
                previous_visible_count=len(data['news']),unique_count=len(unique),split_groups=split_groups,
                dates=dict(dates),date_problem_ids=date_problems,home_page_link_ids=roots,
                search_feed_count=len(plan),eligible_university_count=len(eligible),uncovered_universities=uncovered,
                feeds_per_cycle=config['feeds_per_cycle'],lookback_days=config['lookback_days'],link_checks=[])
    if args.links:
        chosen=[];publishers=Counter();google=0
        for n in sorted(raw,key=lambda n:bool(n.get('original_url')),reverse=True):
            if urlsplit(n.get('original_url') or n['url']).hostname=='news.google.com':
                if google>=3:continue
                google+=1
            elif publishers[n['source']]>=3:continue
            else:publishers[n['source']]+=1
            chosen.append(n)
            if len(chosen)>=12:break
        with ThreadPoolExecutor(max_workers=3) as pool:result['link_checks']=list(pool.map(check_link,chosen))
    (ROOT/'site_integrity_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('split_groups','link_checks')},ensure_ascii=True))
    print('Split groups:',len(split_groups),'Links checked:',len(result['link_checks']))

if __name__=='__main__':main()
