"""대학 주소록에 없는 지자체 운영 교육과정의 확인된 관할 지역."""
import re
import json
from pathlib import Path
from collections import defaultdict

DIRECTORY = json.loads((Path(__file__).resolve().parent/'municipalities.json').read_text(encoding='utf-8'))
LOCALITIES = defaultdict(list)
for record in DIRECTORY['records']:
    LOCALITIES[record['name']].append(record)
PROGRAM = r'(?:농업(?:인)?|노인(?:지도자|복지)?|시민|군민|여성|박물관|평생학습|혁신)\s*대학'


def select_locality(name, known_regions):
    candidates = LOCALITIES[name]
    regions = {r['region'] for r in candidates}
    if len(regions)>1:
        candidates = [r for r in candidates if r['region'] in known_regions]
    return candidates if len({r['region'] for r in candidates})==1 else []


def campus_locality(label,known_regions=()):
    stem=re.sub(r'\s+','',label).removesuffix('캠퍼스')
    stem=re.sub(r'(?:글로컬|글로벌|메디컬)$','',stem)
    stem=stem.removesuffix('공동')
    provinces={'서울':'서울','부산':'부산','대구':'대구','인천':'인천','광주':'광주','대전':'대전','울산':'울산','세종':'세종','경기':'경기도','경기도':'경기도','강원':'강원','충북':'충북','충남':'충남','전북':'전북','전남':'전남','경북':'경북','경남':'경남','제주':'제주'}
    if stem in provinces:
        return dict(name=label,region=provinces[stem],locality=stem,source=DIRECTORY['source'])
    candidates=[record for name,records in LOCALITIES.items() if name==stem or name[:-1]==stem for record in records]
    regions={record['region'] for record in candidates}
    if len(regions)>1:candidates=[r for r in candidates if r['region'] in known_regions]
    if len({r['region'] for r in candidates})!=1:return None
    record=candidates[0]
    return dict(name=label,region=record['region'],locality=record['name'],source=DIRECTORY['source'])


def local_education_context(title, summary='', known_regions=()):
    """자료 출처나 기사 ID와 무관한 공통 지자체/교육과정 분류."""
    evidence, programs = [], []
    def add(record, text, method, reason):
        if not any(p['region']==record['region'] and p['reason']==reason for p in evidence):
            evidence.append(dict(region=record['region'],text=text,method=method,reason=reason,
                                 source=DIRECTORY['source'],locality=record['name']))
    for name in LOCALITIES:
        if name[:-1] not in title and name not in summary:
            continue
        candidates = select_locality(name,set(known_regions))
        if not candidates:
            continue
        record = candidates[0]
        direct = re.search(re.escape(name[:-1])+r'\s*(?:'+re.escape(name[-1])+r'\s*)?'+PROGRAM,title)
        title_actor = False
        for match in re.finditer(r'(?<![가-힣])'+re.escape(name),title):
            suffix = title[match.end():]
            participant = re.match(r'\s*(?:출신|거주|에서\s*온|참가자)',suffix)
            if participant:
                continue
            actor = match.start()<25 and re.match(r'(?:청)?\s*(?:[,，]|은\b|는\b|수(?:가|는)?(?:\s|[,，]))',suffix)
            if not actor and match.start()<25:
                actor=re.match(r'\s+[가-힣\s]{0,18}(?:장학재단|교육재단|문화재단|평생학습관)',suffix)
            venue = re.match(r'(?:에서|서)\s*.{0,35}(?:열리|열린|개최|개막|진행)',suffix)
            if actor or venue:
                title_actor = bool(actor) or title_actor
                add(record,match.group(),'title_region','주관 지자체' if actor else '행사 개최 장소')
        program = direct or (re.search(PROGRAM,title) if title_actor else None)
        if program:
            label = re.sub(r'\s+','',direct.group()) if direct else name+re.sub(r'\s+','',program.group())
            programs.append(dict(name=label,region=record['region'],locality=name,source=DIRECTORY['source'],kind='지자체 운영 교육과정'))
            add(record,program.group(),'title_region','지역 교육과정의 관할 지자체')
        # 요약에서는 개최 장소 또는 주관기관인 것이 명확해야 합니다.
        for sentence in re.split(r'[.!?。\n]',summary):
            if re.search(re.escape(name)+r'(?:에서\s*온|\s*출신|에\s*거주)',sentence):
                continue
            match=re.search(r'(?<![가-힣])'+re.escape(name)+r'(?:에서|서)\s*.{0,35}(?:열리|열린|개최|개막|진행)',sentence)
            if match:
                add(record,name,'summary_region','행사 개최 장소')
    return evidence,programs
