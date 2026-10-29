"""대학명·약칭과 소재지 사전. 새 대학은 아래 목록에 추가합니다."""
import re
import json
from pathlib import Path
from campus_addresses import CAMPUS_SELECTORS, SUPPLEMENTS
from local_education import local_education_context,campus_locality
from university_aliases import generate_aliases
from collections import defaultdict
from named_affiliations import extract_facilities
from article_categories import classify_category

# 복수 지역은 캠퍼스가 특정되지 않았을 때의 후보 지역입니다.
GROUPS = {
    '서울': ['서울대학교', '숭실대학교', '서경대학교', '삼육대학교', '서강대학교', '국민대학교', '동덕여자대학교', '덕성여자대학교', '서울여자대학교', '성신여자대학교', '숙명여자대학교', '이화여자대학교', '서울시립대학교', '서울과학기술대학교', '한국체육대학교', '한국성서대학교', '한성대학교', '성공회대학교'],
    '경기도': ['아주대학교', '한신대학교', '한국공학대학교', '수원대학교', '안양대학교', '평택대학교', '용인대학교', '강남대학교', '성결대학교', '차의과학대학교'],
    '인천': ['인천대학교', '인하대학교'],
    '부산': ['부경대학교', '동아대학교', '동의대학교', '동서대학교', '신라대학교', '부산외국어대학교', '국립한국해양대학교', '경성대학교', '부산가톨릭대학교'],
    '대구': ['대구보건대학교', '대구과학대학교', '계명대학교', '계명문화대학교'],
    '광주': ['호남대학교', '조선대학교', '광주대학교', '광주여자대학교', '광주교육대학교'],
    '대전': ['충남대학교', '한남대학교', '목원대학교', '우송대학교', '한국과학기술원'],
    '울산': ['울산대학교', '울산과학대학교', '울산과학기술원'],
    '강원': ['강원대학교', '한림대학교', '상지대학교', '국립강릉원주대학교'],
    '충북': ['충북대학교', '국립한국교통대학교', '서원대학교', '청주대학교', '세명대학교'],
    '충남': ['선문대학교', '호서대학교', '순천향대학교', '남서울대학교', '백석대학교', '한국기술교육대학교', '국립공주대학교'],
    '전북': ['전북대학교', '원광대학교', '전주대학교', '국립군산대학교', '우석대학교'],
    '전남': ['국립순천대학교', '동신대학교', '국립목포대학교', '목포해양대학교', '초당대학교', '한국에너지공과대학교'],
    '경북': ['영남대학교', '한동대학교', '포항공과대학교', '대구대학교', '대구가톨릭대학교', '대구한의대학교', '국립금오공과대학교', '경일대학교'],
    '경남': ['경남대학교', '경상국립대학교', '국립창원대학교', '인제대학교', '영산대학교'],
    '제주': ['제주대학교', '제주한라대학교', '제주관광대학교'],
}
MULTI = {
    '명지대학교': ['서울', '경기도'], '한양대학교': ['서울', '경기도'],
    '고려대학교': ['서울', '세종'], '연세대학교': ['서울', '인천', '강원'],
    '가천대학교': ['경기도', '인천'], '경기대학교': ['경기도', '서울'],
    '성균관대학교': ['서울', '경기도'], '경희대학교': ['서울', '경기도'],
    '한국외국어대학교': ['서울', '경기도'], '중앙대학교': ['서울', '경기도'],
    '건국대학교': ['서울', '충북'], '동국대학교': ['서울', '경기도', '경북'],
    '홍익대학교': ['서울', '세종'], '단국대학교': ['경기도', '충남'],
    '상명대학교': ['서울', '충남'], '경동대학교': ['경기도', '강원'],
    '부산대학교': ['부산', '경남'], '전남대학교': ['광주', '전남'],
    '경북대학교': ['대구', '경북'], '건양대학교': ['대전', '충남'],
}
EXTRA_ALIASES = {
    '인천대학교': ['국립인천대학교','국립인천대'],
    '인하공업전문대학': ['인하공전'],
    '국립한국교통대학교': ['교통대'],
    '서울과학기술대학교': ['서울과기대'], '한국외국어대학교': ['한국외대'],
    '한국과학기술원': ['KAIST', '카이스트'], '울산과학기술원': ['UNIST','유니스트'],
    '광주과학기술원': ['GIST','지스트'],
    '대구경북과학기술원': ['DGIST','디지스트'],
    '포항공과대학교': ['포스텍', 'POSTECH', '포항공대'],
    '한국에너지공과대학교': ['한국에너지공대', 'KENTECH'],
    '차의과학대학교': ['차의과학대', '차의과대학', '차 의과학대학교', '차 의과학대'],
    '부경대학교': ['국립부경대', '국립부경대학교'],
    '부산과학기술대학교': ['부산과기대'],
    '한국기술교육대학교': ['한기대','KOREATECH'],
    '한국체육대학교': ['한체대'],
    '한국예술종합학교': ['한예종'],
}
CAMPUS_RULES = {
    '한양대학교': {'ERICA': '경기도', '에리카': '경기도', '서울캠퍼스': '서울'},
    '연세대학교': {'미래캠퍼스': '강원', '국제캠퍼스': '인천', '신촌캠퍼스': '서울', '(미래)': '강원'},
    '고려대학교': {'세종캠퍼스': '세종', '(세종)': '세종', '서울캠퍼스': '서울'},
    '건국대학교': {'글로컬캠퍼스': '충북', 'GLOCAL': '충북', '(글로컬)': '충북'},
    '명지대학교': {'자연캠퍼스': '경기도', '인문캠퍼스': '서울'},
    '단국대학교': {'죽전캠퍼스': '경기도', '천안캠퍼스': '충남'},
    '경동대학교': {'메트로폴캠퍼스': '경기도', '메디컬캠퍼스': '강원', '글로벌캠퍼스': '강원'},
    '전남대학교': {'여수캠퍼스': '전남', '광주캠퍼스': '광주'},
    '부산대학교': {'양산캠퍼스': '경남', '밀양캠퍼스': '경남', '부산캠퍼스': '부산'},
    '한국외국어대학교': {'글로벌캠퍼스':'경기도','서울캠퍼스':'서울'},
    '건양대학교': {'메디컬캠퍼스':'대전','글로컬캠퍼스':'충남'},
    '동국대학교': {'와이즈캠퍼스':'경북','WISE캠퍼스':'경북'},
}

REGISTRY = {name: [region] for region, names in GROUPS.items() for name in names}
REGISTRY.update(MULTI)
ADDRESS_RECORDS = {}
DIRECTORY_SOURCE = ''
try:
    directory = json.loads((Path(__file__).resolve().parent / 'university_addresses.json').read_text(encoding='utf-8'))
    DIRECTORY_SOURCE = directory['source']
    canonical_names = {name.removeprefix('국립'): name for name in REGISTRY}
    for record in directory['records']:
        name = canonical_names.get(record['name'].removeprefix('국립'), record['name'])
        ADDRESS_RECORDS.setdefault(name, []).append(record)
    for name, records in ADDRESS_RECORDS.items():
        # 住所가 확인된 대학은 추정 목록 대신 주소의 시·도를 사용합니다.
        REGISTRY[name] = sorted({r['region'] for r in records})
except (OSError, ValueError, KeyError, TypeError):
    pass
# 국립 표기 전후의 동일 학교를 별도 후보로 만들면 약칭이 모호해집니다.
for national in list(REGISTRY):
    base=national.removeprefix('국립')
    if national.startswith('국립') and base in REGISTRY:
        entries=ADDRESS_RECORDS.setdefault(national,[])
        for record in ADDRESS_RECORDS.pop(base,[]):
            if not any(r['address']==record['address'] for r in entries):entries.append(record)
        REGISTRY[national]=sorted(set(REGISTRY[national])|set(REGISTRY.pop(base)))
REGISTRY['한국폴리텍대학']=[]  # 캠퍼스가 명시되지 않으면 소재지를 임의 지정하지 않습니다.
for supplement in SUPPLEMENTS:
    entries = ADDRESS_RECORDS.setdefault(supplement['name'], [])
    if not any(r['address'] == supplement['address'] for r in entries):
        entries.append(supplement)
    REGISTRY[supplement['name']] = sorted({r['region'] for r in entries})


def compact(value):
    return re.sub(r'\s+', '', value).lower()


def campus_options(name):
    options = []
    records = ADDRESS_RECORDS.get(name, [])
    for label, aliases, road in CAMPUS_SELECTORS.get(name, []):
        matched = [r for r in records if compact(road) in compact(r['address'])]
        options.append(dict(label=label, aliases=aliases, records=matched))
    known = {compact(alias) for option in options for alias in option['aliases']}
    for alias, region in CAMPUS_RULES.get(name, {}).items():
        if compact(alias) in known:
            continue
        candidates = [r for r in records if r['region'] == region]
        label = alias.strip('()')
        local = [r for r in candidates if label.removesuffix('캠퍼스') in r['address'] or label in r['original_name']]
        # 같은 시·도에 캠퍼스가 여럿이면 주소를 임의로 고르지 않습니다.
        options.append(dict(label=label if label.endswith('캠퍼스') else label+'캠퍼스',
                            aliases=[alias], records=local or (candidates if len(candidates)==1 else [])))
    for record in records:
        for label in re.findall(r'\(([^)]+)\)', record.get('original_name','')):
            if label in ('본교', '분교') or compact(label) in known:
                continue
            options.append(dict(label=label+'캠퍼스', aliases=['('+label+')', label+'캠퍼스'], records=[record]))
        # 기사에 시·군 이름의 캠퍼스가 나오면 대학 주소의 시·군과 직접 대조합니다.
        parts=record['address'].split()
        if len(parts)>1 and parts[1].endswith(('시','군')):
            label=parts[1][:-1]+'캠퍼스'
            options.append(dict(label=label,aliases=[label],records=[record]))
    return options
ALIAS_CANDIDATES = defaultdict(set)
for name in REGISTRY:
    aliases = generate_aliases(name,EXTRA_ALIASES.get(name, []))
    for alias in aliases:
        ALIAS_CANDIDATES[compact(alias)].add(name)
# 폴리텍은 학교 번호보다 기사에 등장하는 캠퍼스명을 주소 레코드와 대조합니다.
for name, records in ADDRESS_RECORDS.items():
    if name.startswith('한국폴리텍'):
        for record in records:
            campus = re.search(r'([가-힣]+)캠퍼스?$', record['original_name'])
            if campus:
                label = campus.group(1)
                variants=[f'{label}폴리텍',f'{label}폴리텍대',f'{label}폴리텍대학']
                variants += [f'{prefix} {label}캠퍼스' for prefix in ['폴리텍','폴리텍대','폴리텍대학','한국폴리텍','한국폴리텍대','한국폴리텍대학']]
                for alias in variants:
                    ALIAS_CANDIDATES[compact(alias)].add(name)
# 띄어쓰기 유무가 달라도 같은 대학을 인식합니다.
ALIASES = {alias:next(iter(names)) for alias,names in ALIAS_CANDIDATES.items() if len(names)==1}
ALIASES_BY_SCHOOL=defaultdict(list)
for alias,name in ALIASES.items():ALIASES_BY_SCHOOL[name].append(alias)
# 가장 긴 대학명부터 매칭하여 '남서울대'를 '서울대'로 인식하지 않게 합니다.
PATTERN = re.compile(r'(?<![가-힣a-zA-Z0-9])(' + '|'.join(r'\s*'.join(re.escape(char) for char in a) for a in sorted(ALIAS_CANDIDATES, key=len, reverse=True)) + ')', re.I)


def select_alias_name(match,text):
    key=compact(match.group())
    candidates=ALIAS_CANDIDATES[key]
    tail=text[match.end():]
    before=text[max(0,match.start()-35):match.start()]
    if re.match(r'공원|입구역|역',tail):return None
    if key.endswith('대') and re.match(r'학(?!생|교)',tail):return None
    if key in ('서울대','서울대학교') and (re.match(r'\s*(?:10|열)\s*개(?:\s*만들기)?',tail)
        or re.search(r'(?:10|열)\s*개(?:의)?\s*$',before)):
        return None
    if re.match(r'학소식|학뉴스|학가소식',tail):return None
    # 해외 동명 기관/해외 분교의 소재지를 국내 대학 본교로 연결하지 않습니다.
    if re.search(r'(?:타슈켄트|하노이|호찌민|호치민)\s*$',before):return None
    if key=='교통대' and re.search(r'(?:상하이|베이징|시안|서안|중국)\s*$',before):return None
    if key in ('국제대','국제대학교') and re.match(r'\s*\(\s*VNU[-\s]?HCM',tail,re.I):return None
    if len(candidates)==1:return next(iter(candidates))
    if not re.match(r'^(?:$|[^가-힣A-Za-z]|(?:는|은|가|의|와|과|를|에|에서)(?=$|[^가-힣A-Za-z])|총장|교수|학생)',tail):return None
    explicit={ALIASES[compact(m.group())] for m in PATTERN.finditer(text) if compact(m.group()) in ALIASES}
    named=candidates&explicit
    if len(named)==1:return next(iter(named))
    context=text[max(0,match.start()-35):match.end()+60]
    local_regions=set()
    for region,labels in PLACE_NAMES.items():
        if any(re.search(r'(?<![가-힣])'+re.escape(label)+r'(?=$|[^가-힣]|소재|지역|캠퍼스)',context) for label in labels):
            local_regions.add(region)
    regional={name for name in candidates if set(REGISTRY[name])&local_regions}
    if len(regional)==1:return next(iter(regional))
    campuses={name for name in candidates if any(compact(alias) in compact(context) for option in campus_options(name) for alias in option['aliases'])}
    return next(iter(campuses)) if len(campuses)==1 else None


def resolve_universities(text):
    text,facilities=extract_facilities(text)
    found = {}
    occurrences = list(PATTERN.finditer(text))
    for index, match in enumerate(occurrences):
        name = select_alias_name(match,text)
        if name is None:continue
        end = min(match.end()+180, occurrences[index+1].start() if index+1<len(occurrences) else len(text))
        nearby = text[match.end():end].split('。')[0]
        # ERICA 한양대처럼 캠퍼스가 대학명 바로 앞에 쓰인 경우도 허용합니다.
        start = max(occurrences[index-1].end() if index else 0, match.start()-20)
        prefix = text[start:match.start()]
        options = campus_options(name)
        chosen = [option for option in options if any(
            compact(alias) in compact(nearby) or compact(prefix).endswith(compact(alias))
            for alias in option['aliases'])]
        entry = found.setdefault(name, {'chosen': [], 'unknown': []})
        entry['chosen'].extend(chosen)
        if not chosen:
            unknown = re.findall(r'([가-힣A-Za-z]{2,16})\s*캠퍼스', nearby)
            descriptions = {'현장','고령친화','디지털','가상','온라인','스마트','산학협력','미래','미래형','혁신','오픈','개방','행복','필드','풀리','낭만','직무','기간','다소비','새로운','맞아','가을','듣고','팝업','지하','함께','열린','도심','대학','사흘간','이틀간','아이디어로','중장년일자리','RISE','rise'}
            unknown = [label for label in unknown if label not in descriptions and not label.endswith(('형','는','은','한','들의','의','과','와'))]
            entry['unknown'].extend(label+'캠퍼스' for label in unknown)
    results = []
    shared=re.search(r'([가-힣]{2,5})공동캠퍼스',text.split('\n')[0])
    shared_location=campus_locality(shared.group() if shared else '',())
    for name, entry in found.items():
        chosen = entry['chosen']
        region_evidence=[]
        records = ADDRESS_RECORDS.get(name, [])
        if chosen:
            selected = {r['address']: r for option in chosen for r in option['records']}
            records = list(selected.values())
        elif entry['unknown']:
            records = []
            region_evidence=[location for label in entry['unknown'] if (location:=campus_locality(label,set(REGISTRY[name]))) is not None]
        if chosen and not records:
            region_evidence=[location for option in chosen if (location:=campus_locality(option['label'],set(REGISTRY[name]))) is not None]
        if shared_location and not chosen:
            records=[]
            entry['unknown']=[shared.group()]
            region_evidence=[shared_location]
        regions = sorted({r['region'] for r in records})
        regions=sorted(set(regions)|{location['region'] for location in region_evidence})
        if not chosen and not entry['unknown'] and not records and not region_evidence:
            regions = REGISTRY[name]
        results.append(dict(name=name, regions=regions, records=records,
                            campus_names=sorted({o['label'] for o in chosen} or set(entry['unknown'])),
                            campus_region_evidence=region_evidence,
                            campus_status='matched' if chosen and records else 'region_only' if region_evidence else 'unresolved' if chosen or entry['unknown'] else 'not_specified'))
    for facility in facilities:
        name=facility['school']
        record=dict(name=name,original_name=facility['name'],campus=facility['name'],region=facility['region'],
                    address=facility['address'],source=facility['source'])
        entry=next((u for u in results if u['name']==name),None)
        if entry is None:
            entry=dict(name=name,regions=[],records=[],campus_names=[],campus_region_evidence=[],campus_status='matched')
            results.append(entry)
        entry['regions']=sorted(set(entry['regions'])|{facility['region']})
        if facility['address']:entry['records'].append(record)
        else:
            entry['campus_region_evidence'].append(dict(name=facility['name'],region=facility['region'],source=facility['source']))
            if not entry['records']:entry['campus_status']='region_only'
        entry['campus_names'].append(facility['name'])
        entry['affiliation_type']='university_hospital'
    if any(u['name'].startswith('한국폴리텍') and u['name']!='한국폴리텍대학' for u in results):
        results=[u for u in results if u['name']!='한국폴리텍대학']
    return results


def match_universities(text):
    return [(u['name'], u['regions']) for u in resolve_universities(text)]


PLACE_NAMES = {
    '서울': ['서울특별시', '서울시', '서울'], '부산': ['부산광역시', '부산시', '부산'],
    '대구': ['대구광역시', '대구시', '대구'], '인천': ['인천광역시', '인천시', '인천'],
    '광주': ['광주광역시', '광주'], '대전': ['대전광역시', '대전시', '대전'],
    '울산': ['울산광역시', '울산시', '울산'], '세종': ['세종특별자치시', '세종시', '세종'],
    '경기도': ['경기도'], '강원': ['강원특별자치도', '강원도', '강원'],
    '충북': ['충청북도', '충북'], '충남': ['충청남도', '충남'],
    '전북': ['전북특별자치도', '전라북도', '전북'], '전남': ['전라남도', '전남'],
    '경북': ['경상북도', '경북'], '경남': ['경상남도', '경남'],
    '제주': ['제주특별자치도', '제주도', '제주시', '제주'],
}

FOREIGN_NAMES = [
    '미국', '영국', '일본', '중국', '독일', '프랑스', '캐나다', '호주', '뉴질랜드',
    '베트남', '태국', '인도네시아', '말레이시아', '싱가포르', '필리핀', '인도',
    '네팔', '몽골', '대만', '홍콩', '우즈베키스탄', '카자흐스탄', '스페인',
    '이탈리아', '폴란드', '스위스', '네덜란드', '스웨덴', '핀란드', '덴마크',
    '러시아', '우크라이나', '튀르키예', '브라질', '멕시코', '남아프리카공화국',
    '해외', '외국', '호치민', '하노이', '타슈켄트', '마카오',
]
FOREIGN_UNIVERSITIES = ['하버드대', '하버드대학교', '스탠퍼드대', '스탠포드대',
                        '리하이대','리하이대학교','연변대학',
                        '옥스퍼드대', '케임브리지대', '캠브리지대', '엑시터대',
                        '매사추세츠공과대', '예일대', '프린스턴대', '도쿄대', '교토대',
                        '존스홉킨스', '존스 홉킨스', '존즈홉킨스', '존즈 홉킨스']
CLASSIFICATION_VERSION = 4


def remove_background_affiliations(title, summary):
    """학력/출신 기관을 임용·발표 등 기사의 현재 소속과 구분합니다."""
    ignored=[]
    sentences=re.split(r'(?<=[.!?。])\s+',summary)
    cleaned=[]
    for sentence in sentences:
        occurrences=list(PATTERN.finditer(sentence))
        replacements=[]
        for i,match in enumerate(occurrences):
            end=occurrences[i+1].start() if i+1<len(occurrences) else len(sentence)
            after=sentence[match.end():min(end,match.end()+100)]
            before=sentence[max(0,match.start()-15):match.start()]
            # 평생교육원 수료식이나 복수학위 협약을 인물의 과거 학력으로 지우지 않습니다.
            education=re.search(r'^(?:\s*(?:에서|의))?\s*(?:[가-힣]+(?:학과|학부|대학원)(?:에서|의)?\s*)?(?:를?\s*졸업(?:한|했|하고)|출신|동문(?:인|으로)|수료(?:한|했)|(?:학사|석사|박사)(?:와\s*(?:학사|석사|박사))*\s*학위|학위.{0,12}(?:받|취득))',after)
            prior=re.search(r'(?:졸업한|출신인|학위를\s*받은)\s*$',before)
            if education or prior:
                name=select_alias_name(match,sentence)
                if name is None:continue
                ignored.append(dict(name=name,reason='인물의 학력·출신 대학'))
                replacements.append((match.start(),match.end()))
        for start,end in reversed(replacements):sentence=sentence[:start]+' '+sentence[end:]
        cleaned.append(sentence)
    return '\n'.join(cleaned),ignored


def foreign_subject_names(title):
    names=[]
    if re.search(r'국제대(?:학교)?\s*\(VNU[-\s]?HCM\)',title,re.I):names.append('국제대학교(VNU-HCM)')
    if re.search(r'타슈켄트\s*아주대(?:학교)?',title):names.append('타슈켄트 아주대학교')
    for alias in sorted(FOREIGN_UNIVERSITIES,key=len,reverse=True):
        if re.search(r'(?<![가-힣A-Za-z])'+re.escape(alias),title):
            name='존스홉킨스대학교' if '홉킨스' in alias else alias[:-1]+'대학교' if alias.endswith('대') else alias
            if name=='스탠포드대학교':name='스탠퍼드대학교'
            if name not in names and not any(alias in n for n in names):names.append(name)
    return names


INTERNATIONAL_ACTION = r'교류|협약|협력|공동\s*연구|공동\s*교육|방문|파견|유학|유학생|연수|진출|해외|국제캠퍼스'
REFERENCE_CONTEXT = r'사례|비교|참고|반면|달리|벤치마킹'


def foreign_region_evidence(text, method):
    # 요약은 제목에서 국제 활동이 확인된 경우에만 호출합니다.
    # 국내 대학 기사의 해외 사례 비교는 해외 활동 기사와 구분합니다.
    if PATTERN.search(text) and re.search(REFERENCE_CONTEXT, text) and not re.search(INTERNATIONAL_ACTION, text):
        return []
    if PATTERN.search(text) and re.search(r'(?:해외|외국|베트남|중국|일본|인도네시아)\s*(?:학습생|참가자|유학생|대학생)',text) and not re.search(r'교류|협약|협력|방문|파견|연수|진출|현지|유학박람회|맞손|체결',text):
        return []
    # '중국어', '일본어'처럼 국내 강좌 이름에 포함된 경우를 해외 국가로 보지 않습니다.
    ending = r'(?=$|[^가-힣A-Za-z]|(?:에서|의|와|과|는|은|에|로|를|을)(?=$|[^가-힣A-Za-z])|대학|유학|캠퍼스|현지|(?:국립|관광|공과|의과|경제|과학|사범|명문)(?:대학|대))'
    for name in FOREIGN_NAMES:
        match = re.search(r'(?<![가-힣A-Za-z])' + re.escape(name) + ending, text)
        if match:
            sentence = re.split(r'[.!?。\n]', text[:match.start()])[-1] + text[match.start():].split('.')[0]
            if re.search(REFERENCE_CONTEXT, sentence) and not re.search(INTERNATIONAL_ACTION, sentence):
                continue
            if re.search(r'대학|캠퍼스|유학|' + INTERNATIONAL_ACTION, sentence):
                return [dict(region='해외', text=name, method=method, reason='해외 대학 또는 국제 활동 문맥')]
    for name in FOREIGN_UNIVERSITIES:
        if re.search(r'(?<![가-힣A-Za-z])' + re.escape(name), text):
            return [dict(region='해외', text=name, method=method)]
    abbreviation = re.search(r'(?<![가-힣A-Za-z])[美英日中獨佛](?=\s*(?:대학|캠퍼스|유학|[가-힣A-Za-z]{1,20}대(?:학교)?(?=$|[^가-힣A-Za-z])))', text)
    return [dict(region='해외', text=abbreviation.group(), method=method)] if abbreviation else []


def explicit_title_regions(title, method='title_region', include_foreign=True):
    found = []
    # 대학명 일부(경남대, 서울시립대 등)를 지역명으로 중복 해석하지 않습니다.
    without_schools = PATTERN.sub(lambda m:' ' if select_alias_name(m,title) else m.group(), title)
    without_schools = re.sub(r'(?:서울특별시|서울시|서울)\s*(?:출신|거주(?:자|민)?|원정(?:진료)?|사례|벤치마킹)', ' ', without_schools)
    # 경기도 광주시는 광주광역시와 다릅니다.
    without_schools = re.sub(r'(경기도\s*)광주시?', r'\1', without_schools)
    boundary = r'(?=$|[^가-힣A-Za-z]|(?:에서|에서도|서|으로|는|은|가|의|와|과|를|을|에|로)(?=$|[^가-힣A-Za-z])|지역|소재|교육청|도청|시청|도지사|시의회|캠퍼스|도(?=[^가-힣]|$)|권(?=\s*대학)|형(?=\s*(?:대학|캠퍼스|교육)))'
    for region, aliases in PLACE_NAMES.items():
        for alias in aliases:
            pattern = r'(?<![가-힣A-Za-z])' + re.escape(alias) + boundary
            if re.search(pattern, without_schools):
                found.append(dict(region=region, text=alias, method=method))
                break
    # '경기'는 경제·스포츠 의미와 겹치므로 지역 맥락이 명확할 때만 사용합니다.
    if not any(p['region']=='경기도' for p in found) and re.search(r'(?<![가-힣])경기(?=\s*(?:지역|도내|북부|남부|동부|서부|교육청)|[·ㆍ/](?:서울|인천))', without_schools):
        found.append(dict(region='경기도', text='경기', method=method))
    # 지역명이 기관·캠퍼스 이름과 붙어 있어도 인식합니다. 대학명 자체는 위에서
    # 마스킹했으므로 서울대/경남대의 일부를 지역 근거로 중복 사용하지 않습니다.
    institutional = r'(?:(?:문화|경제|산업|관광|교육|특수|평생|창작|상상|글로벌|공동|남부|북부|동부|서부|탄소|불교|감귤|어린이|사회서비스|앵커)[가-힣A-Za-z·\s]{0,20}(?:재단|진흥원|캠퍼스|대학|박물관|교육원|문화원|센터|연구원|농협|사무소|세상|포럼)|TP|테크노파크|경총|지법|시립|시의회|시의원|시민대학|도민(?:행복)?대학|연합회|박물관|귀농귀촌대학|농업(?:인)?대학|형\s*(?:계약학과|미네르바)|도(?=민행복대학))'
    aliases = {alias:region for region,labels in PLACE_NAMES.items() for alias in labels}
    aliases['경기']='경기도'
    for alias,region in sorted(aliases.items(),key=lambda item:len(item[0]),reverse=True):
        if any(p['region']==region for p in found):continue
        if re.search(r'(?<![가-힣A-Za-z])'+re.escape(alias)+r'\s*'+institutional,without_schools):
            found.append(dict(region=region,text=alias,method=method,reason='지역명이 포함된 기관·정책·캠퍼스'))
    if not any(p['region']=='경기도' for p in found):
        match=re.search(r'(?<![가-힣])경기\s+(?:\d+\s*개\s*대학|대학\s*(?:정책|지원|협력)|미래산업)',without_schools)
        if match and not re.search(r'(?:축구|야구|배구|농구|스포츠)\s*$',without_schools[max(0,match.start()-10):match.start()]):
            found.append(dict(region='경기도',text='경기',method=method,reason='지역 대학·정책 문맥'))
    paired_aliases={alias:region for alias,region in aliases.items() if len(alias) in (2,3)}
    pair_pattern='|'.join(re.escape(alias) for alias in sorted(paired_aliases,key=len,reverse=True))
    for pair in re.finditer(r'(?<![가-힣])((?:'+pair_pattern+r'){2,})(?=$|\s|권|지역|앵커|통합특별시|[·,，])',without_schools):
        for token in re.finditer(pair_pattern,pair.group()):
            region=paired_aliases[token.group()]
            if not any(p['region']==region for p in found):
                found.append(dict(region=region,text=token.group(),method=method,reason='연속 표기된 시·도명'))
    if re.search(r'인\s*서울\s*(?:대학|캠퍼스)',without_schools) and not any(p['region']=='서울' for p in found):
        found.append(dict(region='서울',text='인서울',method=method,reason='서울 소재 대학을 뜻하는 표현'))
    if include_foreign:
        found += foreign_region_evidence(title, method)
    return found


def relevant_summary_regions(summary, known_regions, include_foreign):
    evidence = []
    for sentence in re.split(r'[.!?。\n]', summary):
        for place in explicit_title_regions(sentence, 'summary_region', include_foreign):
            if place['region'] == '해외':
                evidence.append(place)
                continue
            alias = re.escape(place['text'])
            position = sentence.find(place['text'])
            context = sentence[position:position+90]
            participant = re.search(r'참여|참가|거주|출신|모집|대상', context)
            host = re.search(r'주최|주관|개최|열리|열린|개막|협약.*체결', context)
            if participant and not host:
                continue
            # 주관 대학/제목의 소재지가 있으면 다른 지역은 명확한 행사 장소나
            # 공동 주관기관일 때만 추가합니다. 참가자 거주지는 소재지가 아닙니다.
            venue = re.search(alias+r'(?:광역시|특별시|도|시)?(?:에서|서)\s*.{0,45}(?:개최|열리|열린|개막|진행|체결)', sentence)
            organizer = re.search(alias+r'(?:청|도청|시청|교육청)?(?:은|는|이|가|와|과|,|\s).{0,35}(?:주최|주관|협약.*체결)', sentence)
            if known_regions and place['region'] not in known_regions and not (venue or organizer):
                continue
            place['reason'] = '행사 개최 장소' if venue else '공동 주관기관' if organizer else '주관 지역 보완'
            evidence.append(place)
    return evidence


def reclassify_article(item):
    subject_summary,background = remove_background_affiliations(item['title'],item.get('body',''))
    matches = resolve_universities(item['title'] + '\n' + subject_summary)
    foreign_subjects=foreign_subject_names(item['title'])
    newsroom_school=''
    if not matches and not foreign_subjects:
        # 공식 뉴스룸은 학과·부서 이름만 제목에 쓰기도 하므로 발행 대학을 보완합니다.
        publisher=compact(item.get('source',''))
        newsroom_school=next((name for name in REGISTRY
                              if publisher in (compact(name),compact(name+'뉴스룸'),compact(name+'공식뉴스룸'))),'')
        if newsroom_school:
            matches=resolve_universities(newsroom_school+'\n'+item['title']+'\n'+subject_summary)
    mentioned = explicit_title_regions(item['title'])
    base_regions={r for university in matches for r in university['regions']} | {p['region'] for p in mentioned}
    local_evidence, programs = local_education_context(item['title'], item.get('body',''),base_regions)
    for place in local_evidence:
        if not any(p['region']==place['region'] for p in mentioned):
            mentioned.append(place)
    title_regions = {p['region'] for p in mentioned}
    known_regions = {r for university in matches for r in university['regions']} | (title_regions-{'해외'})
    # RSS 요약의 단순한 국가명 언급만으로 해외를 부여하지 않습니다.
    summary_foreign = bool(re.search(INTERNATIONAL_ACTION+r'|임용|부임|취임|영입', item['title']))
    summary_places = relevant_summary_regions(subject_summary, known_regions, include_foreign=summary_foreign)
    for place in summary_places:
        if not any(p['region']==place['region'] for p in mentioned):
            mentioned.append(place)
    if not any(p['region']=='해외' for p in mentioned):
        foreign_subjects=[]
    regions = sorted({region for u in matches for region in u['regions']} | {place['region'] for place in mentioned})
    evidence = []
    for university in matches:
        name, candidates, records = university['name'], university['regions'], university['records']
        campuses = []
        for record in records:
            labels = [o['label'] for o in campus_options(name) if any(r['address']==record['address'] for r in o['records'])]
            campuses.append(dict(name=' / '.join(sorted(set(labels))) or record.get('campus','캠퍼스명 미확인'),
                                 address=record['address'], region=record['region'], source=record.get('source',DIRECTORY_SOURCE)))
        for location in university['campus_region_evidence']:
            campuses.append(dict(name=location['name'],address='',region=location['region'],source=location['source']))
        evidence.append(dict(name=name, regions=candidates,
                             affiliation_type=university.get('affiliation_type','university'),
                             identification_method='official_newsroom' if name==newsroom_school else 'article_text',
                             identification_source=item.get('source','') if name==newsroom_school else '',
                             addresses=sorted({r['address'] for r in records}),
                             source=DIRECTORY_SOURCE if records else '',
                             method='national_network' if name=='한국폴리텍대학' and not candidates else 'address_directory' if records else 'campus_region' if university['campus_status']=='region_only' else 'campus_unresolved' if university['campus_status']=='unresolved' else 'manual_registry',
                             campus_names=university['campus_names'], campus_status=university['campus_status'], campuses=campuses))
    subjects=[u['name'] for u in matches]+foreign_subjects
    school_aliases=sorted({alias for u in matches for alias in ALIASES_BY_SCHOOL[u['name']]})
    return dict(item, school=' · '.join(subjects) or ' · '.join(p['name'] for p in programs) or '대학명 미확인',
                category=classify_category(item['title'],item.get('body','')),
                school_names=subjects, school_aliases=school_aliases,
                regions=regions, region=regions[0] if len(regions) == 1 else '',
                city=' · '.join(regions) or '지역 미분류', universities=evidence, mentioned_regions=mentioned, education_programs=programs,
                classification_status='classified' if regions else 'needs_review', classification_version=CLASSIFICATION_VERSION,
                background_universities=background,foreign_universities=foreign_subjects)
