"""행정안전부의 전국 지자체 누리집 목록을 로컬 분류 기준으로 저장합니다."""
from datetime import datetime, timezone
from html import unescape
import json
from pathlib import Path
import re
from urllib.request import urlopen
from sync_university_addresses import PROVINCES

SOURCE = 'https://www.mois.go.kr/frt/sub/a04/localGovernment/screen.do'


def sync():
    with urlopen(SOURCE, timeout=30) as response:
        html = response.read().decode('utf-8')
    records = []
    groups = re.findall(r'<h3\s+class="location_title"[^>]*>\s*<a[^>]*>([^<]+)</a>\s*</h3>\s*<ul\s+class="location_list"[^>]*>(.*?)</ul>', html, re.S)
    for heading, body in groups:
        province = unescape(re.sub('<[^>]+>', '', heading)).strip()
        for url, label in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', body, re.S):
            name = unescape(re.sub('<[^>]+>', '', label)).strip()
            region = PROVINCES.get(province)
            # 이 사이트의 기존 광주/전남 필터를 유지하며 원자료의 표기도 보관합니다.
            if province == '전남광주통합특별시':
                region = '광주' if name in {'동구','서구','남구','북구','광산구'} else '전남'
            if region and re.fullmatch(r'[가-힣]+[시군구]', name):
                records.append(dict(name=name, region=region, homepage=unescape(url), source_region=province))
    if len(records) < 200:
        raise ValueError('Incomplete municipality directory; old data retained')
    output = dict(source=SOURCE, fetched_at=datetime.now(timezone.utc).isoformat(), records=records)
    path = Path(__file__).resolve().parent / 'municipalities.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(path)
    print(f'Municipality records: {len(records)}; regions: {len({r["region"] for r in records})}')


if __name__ == '__main__':
    sync()
