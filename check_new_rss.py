"""현재 RSS를 새로 읽어 분류를 점검합니다. 사이트 기사 데이터는 변경하지 않습니다."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from urllib.request import Request,urlopen
from classification_monitor import build_report
from rss_collector import parse_feed

ROOT=Path(__file__).resolve().parent

def fetch(source):
    try:
        with urlopen(Request(source['url'],headers={'User-Agent':'CampusOnRSS/1.0'}),timeout=15) as response:
            raw=response.read(2_000_001)
        if len(raw)>2_000_000:raise ValueError('Feed exceeds size limit')
        items=parse_feed(raw,source['name'],source.get('timezone_offset'))
        return items,dict(name=source['name'],ok=True,count=len(items))
    except Exception as exc:return [],dict(name=source['name'],ok=False,error=f'{type(exc).__name__}: {exc}')

def main():
    sources=[s for s in json.loads((ROOT/'rss_sources.json').read_text(encoding='utf-8')) if s.get('enabled',True)]
    data=json.loads((ROOT/'.rss-cache.json').read_text(encoding='utf-8'))
    items=[];statuses=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for rows,status in pool.map(fetch,sources):items.extend(rows);statuses.append(status)
    report=build_report(items,[n['id'] for n in data['raw_news']]);report['sources']=statuses
    (ROOT/'fresh_rss_classification_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='cases'},ensure_ascii=True))

if __name__=='__main__':main()
