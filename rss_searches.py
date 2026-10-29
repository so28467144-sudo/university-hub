"""지역·대학별 검색을 생성하고 여러 수집 회차에 나눠 순환합니다."""
from collections import defaultdict
from urllib.parse import urlencode
from university_regions import REGISTRY


def google_feed(name,query):
    url='https://news.google.com/rss/search?'+urlencode(dict(q=query,hl='ko',gl='KR',ceid='KR:ko'))
    return dict(name=name,url=url,enabled=True,expanded=True)


def build_search_plan(config):
    if not config.get('enabled',False):return []
    days=max(1,min(int(config.get('lookback_days',30)),365))
    size=max(1,min(int(config.get('universities_per_query',5)),8))
    by_region=defaultdict(list)
    for name,regions in sorted(REGISTRY.items()):
        if '캠퍼스' in name or '대학원' in name or name.startswith('한국폴리텍'):continue
        if not regions:continue
        # 대학을 여러 검색에 중복 배치하지 않으며 지역 검색은 별도로 유지합니다.
        by_region[regions[0]].append(name)
    region_names={'경기도':'경기','강원':'강원','충북':'충북','충남':'충남','전북':'전북','전남':'전남','경북':'경북','경남':'경남'}
    lanes=[]
    for region,names in sorted(by_region.items()):
        regional=google_feed(f'구글 뉴스 · {region} 대학',f'"{region_names.get(region,region)}" (대학 OR 대학교 OR 캠퍼스) when:{days}d')
        lane=[regional]
        for i in range(0,len(names),size):
            terms=[]
            for name in names[i:i+size]:
                short=name.removeprefix('국립').replace('대학교','대').replace('대학','대')
                terms.extend(['"'+name+'"','"'+short+'"'])
            query='('+' OR '.join(dict.fromkeys(terms))+f') when:{days}d'
            lane.append(google_feed(f'구글 뉴스 · {region} 대학군 {i//size+1}',query))
        lanes.append(lane)
    # 첫 회차부터 여러 지역을 골고루 조회합니다.
    return [lane[i] for i in range(max(map(len,lanes),default=0)) for lane in lanes if i<len(lane)]


def select_search_batch(plan,cursor,limit):
    if not plan:return [],0
    count=min(max(1,int(limit)),len(plan))
    cursor=cursor%len(plan)
    return [plan[(cursor+i)%len(plan)] for i in range(count)],(cursor+count)%len(plan)
