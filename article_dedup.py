"""서로 다른 링크로 들어온 동일 보도의 보수적 중복 판정과 대표 기사 선택."""
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher
import re
import unicodedata
from functools import lru_cache
from university_regions import PATTERN,select_alias_name
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from admission_identity import admission_match, admission_bucket
from rss_summaries import assess_summary, USEFUL_KINDS
from named_affiliations import extract_facilities

PLACEHOLDER = '구글 뉴스에서 수집한 기사입니다.'
STOP = {'운영','개최','발표','추진','진행','전격','본격','성료','대학','대학교','지원','강화','위한','통해'}
EVENT_GENERIC = ('대학일자리플러스센터','대학일자리센터','산학협력단','산학협력','총장직무대리',
                 '업무협약','연구성과','신입생모집','대학원','대학교','청년취업','지역사회')


@lru_cache(maxsize=32768)
def event_features(title,schools):
    text=canonical_title(title,schools)
    for school in sorted(schools,key=len,reverse=True):
        if school not in ('대학 일반','대학명 미확인',''):text=text.replace(normalize(school),' ')
    for word in EVENT_GENERIC:text=text.replace(word,' ')
    # 공백과 가운데점 때문에 같은 주제어가 달라지지 않도록 문자 조각을 비교합니다.
    words=re.findall(r'[가-힣a-z]{2,}',text)
    anchors={w[i:i+5] for w in words for i in range(len(w)-4)}
    bigrams={w[i:i+2] for w in words for i in range(len(w)-1)}
    return anchors,bigrams


def event_signature(item):
    schools=tuple(item.get('school_names') or item.get('school','').split(' · '))
    return event_features(item['title'],schools)


def same_event_topic(first,second):
    anchors_a,terms_a=event_signature(first)
    anchors_b,terms_b=event_signature(second)
    common=anchors_a&anchors_b
    if not common:return False
    # 고유 장소/행사명 자체의 글자는 주제 일치 점수에 중복 계산하지 않습니다.
    anchor_terms={word[i:i+2] for word in common for i in range(4)}
    generic={'일대','인근','주변','조성','추진','개최','진행','발표','위한','통해','한다','으로','에서','대학'}
    remaining_a=terms_a-anchor_terms-generic
    remaining_b=terms_b-anchor_terms-generic
    shared=remaining_a&remaining_b
    return len(shared)>=2 and len(shared)/max(1,min(len(remaining_a),len(remaining_b)))>=.2


def normalize(title):
    title=unicodedata.normalize('NFKC',title).lower()
    title=re.sub(r'\[[^]]+\]', ' ', title)
    title=re.sub(r'전격\s*|본격\s*','',title)
    title=re.sub(r'(?<=\d),(?=\d{3}(?:\D|$))','',title)
    return title


@lru_cache(maxsize=32768)
def canonical_title(title,institutions):
    replacements=[]
    for match in PATTERN.finditer(title):
        name=select_alias_name(match,title)
        if name in institutions:replacements.append((match.start(),match.end(),name))
    for start,end,name in reversed(replacements):title=title[:start]+name+title[end:]
    return normalize(title)


def title_key(item):
    schools=tuple(item.get('school_names') or item.get('school','').split(' · '))
    return canonical_title(item['title'],schools)


def tokens(item):
    return set(re.findall(r'[가-힣a-z0-9]{2,}',title_key(item)))-STOP


def canonical_url(item):
    raw=item.get('original_url') or item.get('url','')
    parts=urlsplit(raw)
    query=[(k,v) for k,v in parse_qsl(parts.query) if not k.lower().startswith(('utm_','fbclid','gclid'))]
    return urlunsplit((parts.scheme,parts.netloc.lower(),parts.path,urlencode(query),''))


def quality(item):
    body=item.get('body','').strip()
    useful_body=body if assess_summary(body,item['title'])[0] in USEFUL_KINDS else ''
    # 실제 RSS 요약의 정보량을 우선하고, 요약이 없으면 제목의 구체성을 비교합니다.
    return (bool(useful_body), len(set(re.findall(r'[가-힣a-zA-Z0-9]{2,}',useful_body))),
            len(useful_body), len(tokens(item)), len(item['title']),
            bool(item.get('original_url')) or not item.get('via_google',False), item.get('date',''),item['id'])


def informative_body(item):
    body=item.get('body','').strip()
    return '' if body.startswith(PLACEHOLDER) else re.sub(r'\W','',normalize(body))


def article_resource(url):
    parts=urlsplit(url)
    # 홈페이지·목록 주소가 같다는 이유만으로 서로 다른 기사를 합치지 않습니다.
    if not parts.netloc:return False
    ids={key.lower() for key,value in parse_qsl(parts.query) if value}
    if ids&{'id','idxno','articleno','article_id','news_id','no','seq','nttno','nttid'}:return True
    return bool(parts.path.strip('/')) and not re.fullmatch(r'/(?:news|newsroom|press|index(?:\.html|\.do)?|news/index\.do)/?',parts.path,re.I)


def conflicting_event_numbers(first,second):
    patterns=(r'(20\d{2})',r'(\d+)회',r'(\d+)기',r'(\d+)일',r'(\d+)명',r'(\d+)건',r'(\d+)만원',r'(\d+)%')
    a,b=normalize(first['title']),normalize(second['title'])
    for pattern in patterns:
        left,right=set(re.findall(pattern,a)),set(re.findall(pattern,b))
        if left and right and left!=right:return True
    # A number without a known detail role (LOOK 3, project 2, etc.) is not
    # discarded as if it were an optional attendance count.
    def residual(text):
        text=re.sub(r'\d+\s*[~∼-]\s*\d+일','',text)
        for pattern in patterns:text=re.sub(pattern,'',text)
        return set(re.findall(r'\d+',text))
    return residual(a)!=residual(b)


@lru_cache(maxsize=32768)
def hospital_names(title):
    rest,records=extract_facilities(title)
    return frozenset({r['name'] for r in records}|{n.replace('대학교','대') for n in re.findall(r'[가-힣A-Za-z]{2,25}병원',rest)})


def same_story(first,second,compatibility_only=False):
    hospitals_a,hospitals_b=hospital_names(first['title']),hospital_names(second['title'])
    if hospitals_a and hospitals_b and hospitals_a!=hospitals_b:return False
    admission=admission_match(first,second)
    if admission is False:return False
    url=canonical_url(first)
    if url and url==canonical_url(second) and article_resource(url):return True
    if re.search(r'\[(?:포토|사진|사진뉴스|PHOTO)',first['title']+' '+second['title'],re.I):return False
    if first.get('date') and second.get('date'):
        try:
            if abs((datetime.fromisoformat(first['date'])-datetime.fromisoformat(second['date'])).total_seconds())>72*3600:return False
        except (TypeError,ValueError):return False
    else:
        # 날짜 미상 기사는 동일 제목/기관일 때만 합칩니다.
        if normalize(first['title'])!=normalize(second['title']):return False
    generic=lambda n:re.sub(r'\W','',normalize(n['title'])) in {'월영소식','대학소식','교내뉴스','보도자료','새소식','뉴스레터','공지사항'}
    if generic(first) or generic(second):
        body_a,body_b=informative_body(first),informative_body(second)
        if min(len(body_a),len(body_b))<80 or body_a!=body_b:return False
    activity=lambda title:{key for key,pattern in (
        ('lecture',r'특강|강연'),('performance',r'공연|음악회|연주회'),
        ('cooking',r'김밥|요리체험|음식체험'),('agreement',r'협약|협정|MOU')) if re.search(pattern,title,re.I)}
    activities_a,activities_b=activity(first['title']),activity(second['title'])
    if activities_a and activities_b and not activities_a.intersection(activities_b):return False
    institutions=lambda n:set(n.get('school','').split(' · '))-{'','대학 일반','대학명 미확인'}
    a,b=institutions(first),institutions(second)
    if a and b and not a.intersection(b):return False
    campus_map=lambda n:{u['name']:set(u.get('campus_names',[])) for u in n.get('universities',[]) if u.get('campus_status') in ('matched','region_only') and u.get('campus_names')}
    campus_a,campus_b=campus_map(first),campus_map(second)
    if any(not campus_a[name].intersection(campus_b[name]) for name in campus_a.keys()&campus_b.keys()):return False
    if admission is True:
        # Date, institution and explicit campus protections have already passed.
        left,right=informative_body(first),informative_body(second)
        if min(len(left),len(right))>=120 and SequenceMatcher(None,left,right,autojunk=False).ratio()<.35:
            return False
        return True
    action=lambda title:{word for word in ('취소','철회','반박','후속','연기','모집','추가모집','수상','협약','결과발표','결과공개','마감') if word in re.sub(r'\s+','',title)}
    if action(first['title'])!=action(second['title']):return False
    if set(re.findall(r'\d+',normalize(first['title'])))!=set(re.findall(r'\d+',normalize(second['title']))):
        if not same_event_topic(first,second) or conflicting_event_numbers(first,second):return False
    quoted=lambda title:{re.sub(r'\W','',s) for s in re.findall(r'[‘\'“"]([^’\'”"]{5,80})[’\'”"]',title) if re.search(r'과정|프로그램|포럼|행사|공모전',s)}
    qa,qb=quoted(first['title']),quoted(second['title'])
    if qa and qb and not qa.intersection(qb):return False
    if compatibility_only:return True
    body_a,body_b=informative_body(first),informative_body(second)
    if min(len(body_a),len(body_b))>=120 and SequenceMatcher(None,body_a,body_b,autojunk=False).ratio()<.35:
        return False
    if min(len(body_a),len(body_b))>=80 and SequenceMatcher(None,body_a,body_b,autojunk=False).ratio()>=.88:
        return True
    construction=r'조성|지구단위계획|특화거리|문화거리|창업.*(?:거리|대학가)'
    places=lambda title:set(re.findall(r'([가-힣]{2,20}(?:입구역|시장거리))',title))
    if places(first['title'])&places(second['title']) and all(re.search(construction,n['title']) for n in (first,second)):
        return True
    if first.get('date') and second.get('date') and same_event_topic(first,second):return True
    ta,tb=tokens(first),tokens(second)
    if not ta or not tb:return False
    overlap=len(ta&tb)/min(len(ta),len(tb))
    if a.intersection(b) and any(len(q)>=10 for q in qa.intersection(qb)) and len(ta&tb)>=3:
        return True
    ca=re.sub(r'\W','',title_key(first));cb=re.sub(r'\W','',title_key(second))
    if ca==cb:return True
    # 기관이 없는 일반 정책 보도는 제목이 거의 일치할 때만 병합합니다.
    if not a.intersection(b):
        return overlap>=.95 and SequenceMatcher(None,ca,cb).ratio()>=.94
    return len(ta&tb)>=3 and overlap>=.9 and (
        min(len(ca),len(cb))>=20 and (ca in cb or cb in ca)
        or SequenceMatcher(None,ca,cb).ratio()>=.78)


def deduplicate(items):
    ordered=sorted(items,key=quality,reverse=True)
    # 같은 제목부터 처리해 먼저 들어온 유사 제목 때문에 완전 중복이 갈라지는 것을 막습니다.
    title_buckets={}
    for item in ordered:
        key=re.sub(r'\W','',title_key(item))
        title_buckets.setdefault(key,[]).append(item)
    ordered=[item for bucket in title_buckets.values() for item in bucket]
    groups=[]
    index=defaultdict(set)
    for item in ordered:
        terms=tokens(item)
        url=canonical_url(item)
        if url:terms.add('@url:'+url)
        terms.add('@title:'+normalize(item['title']))
        terms.add('@compact:'+re.sub(r'\W','',title_key(item)))
        campaign=admission_bucket(item)
        if campaign:terms.add(campaign)
        terms.update('@event:'+anchor for anchor in event_signature(item)[0])
        body=informative_body(item)
        if len(body)>=80:terms.add('@body:'+body)
        candidates=set();shared=defaultdict(int)
        for term in terms:
            if term.startswith('@'):candidates.update(index[term])
            else:
                for i in index[term]:shared[i]+=1
        candidates.update(i for i,count in shared.items() if count>=3)
        selected=None
        for i in sorted(candidates):
            group=groups[i]
            matched=all(same_story(item,other) for other in group)
            if not matched:
                # 모든 기사에 공통 고유명사가 있고 과반의 주제가 맞는 사건 묶음만 확장합니다.
                common=set(event_signature(item)[0])
                for other in group:common.intersection_update(event_signature(other)[0])
                matched=bool(common) and sum(same_event_topic(item,other) for other in group)*2>=len(group) and all(
                    same_story(item,other,compatibility_only=True) for other in group)
            if matched:
                selected=i;break
        if selected is None:
            selected=len(groups);groups.append([])
        groups[selected].append(item)
        for term in terms:index[term].add(selected)
    # 보도 순서에 따라 처음 갈라진 사건 묶음도 공통 고유명사와 교차 주제로 재검사합니다.
    anchor_index=defaultdict(set)
    for i in sorted(range(len(groups)),key=lambda i:len(groups[i]),reverse=True):
        common=set(event_signature(groups[i][0])[0])
        for item in groups[i][1:]:common.intersection_update(event_signature(item)[0])
        candidates=set().union(*(anchor_index[a] for a in common)) if common else set()
        for j in sorted(candidates):
            if not groups[j]:continue
            pairs=[(a,b) for a in groups[i] for b in groups[j]]
            if sum(same_event_topic(a,b) for a,b in pairs)*2<len(pairs):continue
            if not all(same_story(a,b,compatibility_only=True) for a,b in pairs):continue
            shared=set(common)
            for item in groups[j]:shared.intersection_update(event_signature(item)[0])
            if not shared:continue
            groups[i].extend(groups[j]);groups[j]=[];common=shared
        for anchor in common:anchor_index[anchor].add(i)
    # Do not publish transitive majority clusters whose members fail pairwise
    # story checks. Preserve each incompatible original as its own group.
    checked_groups=[]
    for group in groups:
        partitions=[]
        for item in sorted(group,key=quality,reverse=True):
            target=next((part for part in partitions if all(same_story(item,other) for other in part)),None)
            if target is None:partitions.append([item])
            else:target.append(item)
        checked_groups.extend(partitions)
    result=[]
    for group in checked_groups:
        if not group:continue
        representative=max(group,key=quality)
        ids=sorted({n['id'] for n in group})
        result.append(dict(representative,duplicate_ids=ids,duplicate_count=len(ids),
                           dedup_version=3,
                           selection_basis='RSS 요약의 정보량 → 제목의 구체성 → 원문 링크 여부 순으로 선택'))
    return sorted(result,key=lambda n:n.get('date',''),reverse=True)


def automatic_merge_exclusion(item):
    """Related coverage and multi-story digests must remain individually visible."""
    return bool(re.search(
        r'칼럼|축사|인터뷰|후속|사설|기고|논평|사직|사의|압수수색|사과|'
        r'브리핑|소식\]|교육소식|이모저모|모음|특별기획|外|\b24시\b|'
        r'참석.*축사|창간|교수의\s*눈', item.get('title',''), re.I))


def confirmed_same_story(first,second):
    """Automatic hiding requires lossless identical published content.

    A matching event/admission identity alone remains a review candidate.
    Requiring all user-visible/searchable fields and links prevents a hidden
    article from adding a unique search, region, date or Excel result.
    """
    if any(automatic_merge_exclusion(x) for x in (first,second)):return False
    if min(len(informative_body(first)),len(informative_body(second)))<120:return False
    fields=('title','body','school','school_names','school_aliases','regions','region',
            'city','category','source','date','url','original_url')
    if any(first.get(k)!=second.get(k) for k in fields):return False
    return bool(canonical_url(first)) and same_story(first,second)


def confirmed_deduplicate(items):
    """Return only proven identical records as representatives; keep other rows."""
    partitions=[]; buckets=defaultdict(list)
    for item in items:
        key=(item.get('title',''),item.get('body',''),canonical_url(item))
        target=next((group for group in buckets[key]
                     if all(confirmed_same_story(item,other) for other in group)),None)
        if target is None:
            target=[];buckets[key].append(target);partitions.append(target)
        target.append(item)
    result=[]
    for group in partitions:
        representative=max(group,key=quality)
        ids=sorted(x['id'] for x in group)
        result.append(dict(representative,duplicate_ids=ids,duplicate_count=len(ids),dedup_version=4))
    return sorted(result,key=lambda n:n.get('date',''),reverse=True)


def duplicate_review_groups(items):
    by_id={x['id']:x for x in items}
    return [dict(representative_id=row['id'],article_ids=row['duplicate_ids'],
                 decision='candidate_only',reason='event similarity is not identity')
            for row in deduplicate(items) if row['duplicate_count']>1
            and not all(confirmed_same_story(by_id[row['id']],by_id[i])
                        for i in row['duplicate_ids'] if i!=row['id'])]


def public_story_groups(items):
    return [dict(version=4,representative_id=row['id'],article_ids=row['duplicate_ids'],
                 basis='identical complete visible content and links')
            for row in confirmed_deduplicate(items) if row['duplicate_count']>1]
