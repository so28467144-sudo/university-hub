"""수집할 때마다 수행하는 분류 무결성 검사와 수동 검토 후보 기록."""
from collections import Counter
from datetime import datetime,timezone
import re

REGIONS={'서울','부산','대구','인천','광주','대전','울산','세종','경기도','강원','충북','충남','전북','전남','경북','경남','제주','해외'}
CATEGORIES={'입시·모집','연구·성과','행사·특강','장학·지원','캠퍼스','대학 소식'}
GENERAL={'국내대학','지역대학','지방대학','전문대학','국립대학','국립대학교','사립대학','세계대학','우리대학','공동대학','공유대학','일반대학','해외대학','선도대학','지원대학','년제대학'}

def inspect_article(item):
    errors=[];review=[]
    regions=set(item.get('regions',[]));universities=item.get('universities',[])
    if not regions.issubset(REGIONS):errors.append('invalid_region')
    if item.get('category') not in CATEGORIES:errors.append('invalid_category')
    if not item.get('classification_version'):errors.append('missing_classification_version')
    expected={r for u in universities for r in u.get('regions',[])}|{p['region'] for p in item.get('mentioned_regions',[])}
    if regions!=expected:errors.append('region_evidence_mismatch')
    if item.get('date'):
        try:
            if datetime.fromisoformat(item['date']).tzinfo is None:errors.append('date_without_timezone')
        except (TypeError,ValueError):errors.append('invalid_date')
    else:review.append('publication_date_missing')
    if any(u.get('campus_status')=='unresolved' for u in universities):review.append('campus_address_unresolved')
    if universities and not regions and any(u.get('method')!='national_network' for u in universities):review.append('identified_school_without_region')
    if not item.get('school_names'):
        names=re.findall(r'(?<![가-힣])([가-힣]{2,}(?:대학교|대학|공전|교대))',item.get('title',''))
        if any(name not in GENERAL and not re.search(r'농업|노인|시민|군민|박물관|평생|여성|도민|지도자|열린대학',name) for name in names):review.append('unrecognized_school_name')
    return errors,review

def build_report(items,known_ids=()):
    rows={n['id']:n for n in items};known=set(known_ids);counts=Counter();cases=[]
    for item in rows.values():
        errors,review=inspect_article(item)
        for reason in errors+review:counts[reason]+=1
        if errors or review:cases.append(dict(id=item['id'],title=item['title'],school=item.get('school'),regions=item.get('regions'),
            new=item['id'] not in known,errors=errors,review_reasons=review,url=item.get('original_url') or item.get('url')))
    return dict(checked_at=datetime.now(timezone.utc).isoformat(),checked_count=len(rows),
                new_count=sum(id not in known for id in rows),updated_count=sum(id in known for id in rows),
                error_count=sum(bool(n['errors']) for n in cases),review_count=sum(bool(n['review_reasons']) for n in cases),
                reasons=dict(counts),cases=cases)
