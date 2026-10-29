"""API 키 없이 공공데이터포털 공개 다운로드에서 대학 주소록을 갱신합니다."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
SOURCE = 'https://www.data.go.kr/data/15107736/standard.do'
PROVINCES = {
    '서울특별시':'서울', '부산광역시':'부산', '대구광역시':'대구', '인천광역시':'인천',
    '광주광역시':'광주', '대전광역시':'대전', '울산광역시':'울산', '세종특별자치시':'세종',
    '경기도':'경기도', '강원도':'강원', '강원특별자치도':'강원', '충청북도':'충북',
    '충청남도':'충남', '전라북도':'전북', '전북특별자치도':'전북', '전라남도':'전남',
    '경상북도':'경북', '경상남도':'경남', '제주특별자치도':'제주',
}


def fetch_json(url):
    with urlopen(Request(url, headers={'User-Agent':'CampusOn university address directory/1.0'}), timeout=30) as response:
        return json.load(response)


def sync():
    header = fetch_json('https://www.data.go.kr/download/columList.json?pk=15107736&ext=JSON')
    params = dict(publicDataPk='15107736', colNmList=header['tableVO']['colNmList'],
                  svcTableNm=header['tableVO']['svcTableNm'], totalCount=header['totalCount'],
                  perPage=10000, page=1)
    raw = fetch_json('https://www.data.go.kr/download/standard.json?' + urlencode(params, doseq=True))
    if not isinstance(raw, list) or len(raw) != header['totalCount']:
        raise ValueError('Incomplete address directory; previous file retained')
    records = []
    seen = set()
    for row in raw:
        # 모대학의 부속 대학원은 본교 레코드와 중복되므로 제외합니다.
        if row.get('UNIV_SE_NM') == '대학원' and ' ' in row.get('SCHL_NM',''):
            continue
        full_name = row.get('SCHL_NM', '').strip()
        name = re.sub(r'\([^)]*\)', '', full_name).strip()
        address = (row.get('LCTN_ROAD_NM_ADDR') or row.get('LCTN_LOTNO_ADDR') or '').strip()
        region = PROVINCES.get(address.split()[0]) if address else None
        if not name or not region:
            continue
        key = (name, address)
        if key in seen:
            continue
        seen.add(key)
        records.append(dict(name=name, original_name=full_name, address=address,
                            region=region, homepage=row.get('HMPG_ADDR',''),
                            data_date=row.get('CRTR_YMD',''), campus=row.get('MAINBRANCH_NM','')))
    if len(records) < 300:
        raise ValueError('Unexpectedly small directory; previous file retained')
    result = dict(source=SOURCE, provider='한국대학교육협의회 / 공공데이터포털',
                  fetched_at=datetime.now(timezone.utc).isoformat(), records=records)
    path = ROOT / 'university_addresses.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)
    print(f'Address records: {len(records)}; unique universities: {len({r["name"] for r in records})}')


if __name__ == '__main__':
    sync()
