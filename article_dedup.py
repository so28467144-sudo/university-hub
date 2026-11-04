"""서로 다른 링크로 들어온 동일 보도의 보수적 중복 판정과 대표 기사 선택."""
from collections import defaultdict
from datetime import datetime, timedelta
from difflib import SequenceMatcher
import re
import unicodedata
from functools import lru_cache
from university_regions import PATTERN,select_alias_name
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from admission_identity import admission_identity, admission_match, admission_bucket
from rss_summaries import assess_summary, USEFUL_KINDS
from named_affiliations import extract_facilities
from local_education import LOCALITIES

PLACEHOLDER = '구글 뉴스에서 수집한 기사입니다.'
STOP = {'운영','개최','발표','추진','진행','전격','본격','성료','대학','대학교','지원','강화','위한','통해'}
EVENT_GENERIC = ('대학일자리플러스센터','대학일자리센터','산학협력단','산학협력','총장직무대리',
                 '업무협약','연구성과','신입생모집','대학원','대학교','청년취업','지역사회')
PRESS_WINDOW_HOURS = 72
PRESS_MIN_TITLE_SHARE = .4
PRESS_LONG_GAP_TITLE_SHARE = .6
PRESS_DISTINCT_TAIL = 3
PRESS_GENERIC = STOP|{'교수','교수팀','연구팀','연구','학생','학생들','재학생','총장','부총장','센터','사업단','행사','프로그램',
                      '교육','협약','체결','선정','수상','기념','모집','참여','확대','신설','취임','임명','머니투데이',
                      '손잡고','손잡아','손잡','맞손','맞힘','나서','나선다','나섰다','연계','협력','함께','앞장','본격','돕는다'}
PHASE_BEFORE = r'예정|연다|열린다|개최한다|앞두고|내달|다음달|오는\d+일|참가자모집|신청접수'
PHASE_AFTER = r'성료|마쳐|마무리|폐막|성황리|열려|열었다|개최했|진행했|배출|수료|마감했'
# ' - 머니투데이', ' > 뉴스', ':중수청일보', ' | 기사' 같은 제목 뒤 꼬리표입니다.
# '-'·'|' 앞에는 공백이 있어야 합니다. 'POP-UP 콘서트 개최'의 '-UP …'은 제목 내용입니다.
TITLE_SUFFIX = r'(?:\s+[-|]\s*[^-|:\s][^-|:]{0,18}|\s*:\s*[^-|:\s][^-|:]{0,18}|\s*>\s*뉴스)\s*$'
IDENTICAL_TITLE_MIN = 8
IDENTICAL_TITLE_LONG_MIN = 20
IDENTICAL_TITLE_LONG_WINDOW_HOURS = 168
# '[인사] 경북대학교'처럼 머리표 뒤 내용이 짧은 제목은 길이 기준으로 걸러집니다. 아래는 내용과 상관없이 늘 묶지 않는 머리표입니다.
GENERIC_TITLE = r'^\s*\[(?:알림|게시판|오늘의\s*운세)\]'
ORGANIZATION_SUFFIX = r'(?:상의|상공회의소|상공회|의회|시청|군청|구청|도청|교육청|교육지원청|재단|진흥원|공사|공단|협회|센터|연구원|의료원|소방서|경찰서|농협|청)'
NEW_FACT_WORDS = r'후속|추가|2차|재개|번복|해명|반박|논란|의혹|수사|고발|소송|징계|합격|결과|취소|철회|연기|사과|입장문'
# 같은 사건 판정(7)의 고유어는 이 수 이하의 주체(대학·기관) 기사에만 나오는 말입니다.
EVENT_ENTITY_MAX_OWNERS = 2
EVENT_SUPPORT_MAX_OWNERS = 10
# 한 주체의 기사에서 이만큼의 서로 다른 날(한국 시간)에 나오는 고유어는 진행 중인 주제로 봅니다.
EVENT_TOPIC_MIN_ARTICLES = 4
CANDIDATE_HIGH_RISK = {'different people','new-fact word differs','incident reported on one side only','announcement vs result',
                       'conflicting numbers','different event types','different hospitals','different campuses',
                       'admission identity uncertain','summary lacks shared entity','different places'}
# 돌발 사건 낱말의 갈래. 같은 갈래의 낱말('체포'·'입건')은 같은 사건을 다르게 쓴 것입니다.
EVENT_INCIDENT_FAMILIES = {'police':('입건','체포','구속','검거'),'harm':('부상','사고','사망','숨져','숨진','별세','추락','붕괴','화재','폭행','실종'),
                           'medical':('확진','입원','수술'),'security':('유출','해킹')}
PLACE_NAMES = set(LOCALITIES)|{'경기도','강원도','충청남도','충청북도','전라남도','전라북도','경상남도','경상북도','제주도'}
# '인천시'·'경남도'·'부산광역시'처럼 시·도 이름도 장소입니다.
PLACE_NAMES |= {short+suffix for short in ('서울','부산','대구','인천','광주','대전','울산','세종','경기','강원','충북','충남','전북','전남','경북','경남','제주')
                for suffix in ('시','도','광역시','특별시','특별자치시','특별자치도')}
# 따옴표 비교 대상인 행사·과정 이름의 끝말입니다.
EVENT_NAME_WORDS = r'축제|페스티벌|포럼|대회|공모전|박람회|캠프|과정|프로그램|전시|콘서트|음악회|세미나|심포지엄|학술대회|아카데미|챌린지'
# 대학명도 첫머리 기관도 없는 일반 기사의 비교 묶음입니다.
GENERAL_OWNER = ('@일반 기사',)
PROVINCE_SHORT = {'서울':'서울','부산':'부산','대구':'대구','인천':'인천','광주':'광주','대전':'대전','울산':'울산','세종':'세종',
                  '경기':'경기도','강원':'강원','충북':'충북','충남':'충남','전북':'전북','전남':'전남','경북':'경북','경남':'경남','제주':'제주'}
PERSON_TITLE_MODIFIERS = {'석좌','차기','신임','전임','현직','명예','초빙','겸임','특임','정년','부총리','자유와','대표','공동','초대','역대'}
PERSON_TITLE = r'(?:의원|시의원|도의원|교수|총장|장관|차관|회장|원장|이사장|씨|작가|기자|박사|소장|단장|군수|구청장|교육감)'
EVENT_ENTITY_GENERIC = {'대학원','대학생','신입생','재학생','졸업생','유학생','교직원','연구진','연구자','연구소','연구단','연구원',
                        '캠퍼스','학년도','기념식','설명회','개막식','입학식','졸업식','시상식','협약식','간담회','세미나','워크숍',
                        '프로그램','경쟁력','지역사회','산학협력','교육과정','학생들','교수진','참가자','관계자','지자체','공동연구',
                        '중학생','고교생','고등학생','초등학생','대학원생','청소년','외국인','지역민','시민들','학부모','클러스터','국내외'}
# 조직 이름 구간: 최대 두 단어 뒤에 조직 단위어가 오는 부분입니다.
EVENT_ORGANIZATION_SPAN = (r'(?:[가-힣a-z0-9]+[\s·ㆍ]+){0,2}[가-힣a-z0-9]*'
                           r'(?:사업단|센터|연구소|연구원|연구단|연구팀|학과|학부|전공|캠퍼스|대학원|병원|재단|위원회|협의회|본부|동아리|단과대학)'
                           r'(?=[^가-힣]|$|[과와은는이가의에도])')
EVENT_ENTITY_ENDING = r'(?:다|까지|부터|으로|에게|하며|하고|해서|한다|된다|했다|해야|하라|해라|하자)$'
EVENT_COMMON_LATIN = {'ai','mou','sw','ict','esg','rise','glocal','ri','it','news','tv','pick','pr','cdn','www','com','co','kr'}
EVENT_KINDS = (('ceremony',r'기념식|개교기념일'),('concert',r'음악회|공연|연주회|콘서트'),('exhibition',r'전시|사진전|특별전'),
               ('festival',r'축제|페스티벌'),('briefing',r'설명회'),('forum',r'포럼|학술대회|학술제|세미나|심포지엄|컨퍼런스|콘퍼런스'),
               ('agreement',r'협약|협정|mou|맞손|손잡'),('award',r'수상|시상|표창|대상'),('appointment',r'연임|선임|취임|임명|선출'),
               ('lecture',r'특강|강연'),('contest',r'경진대회|공모전'),('opening',r'신설|개설|개원|개소'),
               ('declaration',r'선언|선포'))
# 연도는 '2,000여 명'의 2000과 구별해 뒤에 숫자·단위가 붙지 않은 네 자리만 봅니다.
EVENT_NUMBER_PATTERNS = (r'(?<!\d)(20\d{2})(?![\d여명개건원만억천])',r'(\d+)회',r'(\d+)기',r'(\d+)차',r'(\d+)대(?!학)',r'(\d+)주년',r'(\d+)명',r'(\d+)건',
                         r'(\d+)억',r'(\d+)만원',r'(\d+)%',r'(\d+)위')


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
    # '[알립니다]'·'[공지]'는 언론사 자체 공지입니다.
    # '… 외 (10월29일 종합)'은 여러 소식을 모은 기사입니다. 연합뉴스의 '(종합)' 갱신 기사는 해당하지 않습니다.
    # 짧은 낱말은 단어 첫머리에서만 찾습니다. '박사과정'의 '사과', '교사의'의 '사의'는 해당하지 않습니다.
    return bool(re.search(
        r'칼럼|(?<![가-힣])축사|인터뷰|(?<![가-힣])후속|(?<![가-힣])사설|(?<![가-힣])기고|논평|(?<![가-힣])사직|(?<![가-힣])사의|압수수색|(?<![가-힣])사과|'
        r'브리핑|소식\]|교육소식|이모저모|모음|특별기획|外|\b24시\b|'
        r'참석.*축사|창간|교수의\s*눈|\s외\s*[(（]|\d+일\s*종합\)|^\s*\[(?:알립니다|공지)\]', item.get('title',''), re.I))


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


def story_actions(title):
    compact=re.sub(r'\s+','',title)
    return {word for word in ('취소','철회','반박','후속','연기','모집','추가모집','수상','협약','결과발표','결과공개','마감') if word in compact}


def story_phase(title):
    compact=re.sub(r'\s+','',title)
    if re.search(PHASE_AFTER,compact):return 'after'
    if re.search(PHASE_BEFORE,compact):return 'before'
    return ''


def title_identity(item):
    """언론사 꼬리표·괄호·공백·따옴표 차이를 뺀 제목. 대학명을 빼면 남는 내용이 짧은 제목은 비교하지 않습니다."""
    title = item.get('title', '')
    for _ in range(2):
        title = re.sub(TITLE_SUFFIX, '', title)
    title = re.sub(r'^\s*\[(?:단독|속보|종합|영상)\]\s*', '', title)
    key = re.sub(r'[\W_]+', '', normalize(title))
    return key if len(title_rest(item, key)) >= IDENTICAL_TITLE_MIN and not re.search(GENERIC_TITLE, item.get('title', '')) else ''


def title_rest(item, key):
    """제목에서 대학명을 뺀 나머지. 길수록 다른 소식과 우연히 같을 가능성이 낮습니다."""
    rest = key
    for name in item.get('school_names') or item.get('school', '').split(' · '):
        rest = rest.replace(re.sub(r'\W', '', normalize(name)), '')
    return rest


def identical_title_partitions(rows):
    """같은 제목이고 72시간(구체적인 긴 제목은 7일) 안이며 요약이 서로 다른 사건을 말하지 않는 기사끼리 묶습니다."""
    parts = []
    for item in sorted(rows, key=quality, reverse=True):
        def fits(other):
            try:
                gap = abs((datetime.fromisoformat(item['date']) - datetime.fromisoformat(other['date'])).total_seconds())
            except (TypeError, ValueError, KeyError):
                return False
            a, b = informative_body(item), informative_body(other)
            # 칼럼·인터뷰·소식 모음은 같은 매체가 다시 수집된 경우만 같은 기사로 봅니다.
            if (automatic_merge_exclusion(item) or automatic_merge_exclusion(other)) and item.get('source') != other.get('source'):
                return False
            # 지역 매체가 며칠 뒤 같은 보도자료를 그대로 싣는 경우가 많아, 구체적인 긴 제목은 7일까지 같은 기사로 봅니다.
            long_title = len(title_rest(item, title_identity(item))) >= IDENTICAL_TITLE_LONG_MIN
            window = (IDENTICAL_TITLE_LONG_WINDOW_HOURS if long_title else PRESS_WINDOW_HOURS) * 3600
            return gap <= window and not (min(len(a), len(b)) >= 80 and SequenceMatcher(None, a, b, autojunk=False).ratio() < .2)
        target = next((part for part in parts if all(fits(other) for other in part)), None)
        if target is None:
            parts.append([item])
        else:
            target.append(item)
    return parts


def subject_organization(item):
    """'대전상의, …'처럼 제목 첫머리에서 주체로 쓰인 기관명."""
    title=re.sub(r'^\s*\[[^\]]*\]\s*','',normalize(item['title']))
    match=re.match(r'([가-힣a-z0-9]{1,14}'+ORGANIZATION_SUFFIX+r')(?=[\s,·ㆍ\-「『‘“\'"(]|$)',title)
    return match.group(1) if match else ''


def distinctive_terms(item):
    """대학명·주체 기관명과 흔한 직함·사업어를 뺀, 사건을 구별하는 제목 단어."""
    schools=item.get('school_names') or item.get('school','').split(' · ')
    names={re.sub(r'\W','',normalize(n)) for n in schools}|{subject_organization(item)}
    # '지역대학과'와 '지역대학'은 같은 단어입니다. 조사를 떼고 비교합니다.
    stems={re.sub(r'(?<=..)(?:과|와|을|를|은|는|이|가|의|에|에서|으로|로)$','',t) for t in tokens(item)}
    return {t for t in stems if t not in PRESS_GENERIC and not any(t.startswith(n) for n in names if n)}


def press_same_story(first,second):
    """다른 언론사의 같은 사건 보도. 하나라도 불확실하면 묶지 않습니다."""
    if any(automatic_merge_exclusion(x) for x in (first,second)):return False
    if not first.get('date') or not second.get('date'):return False
    schools=lambda n:set(n.get('school_names') or [])
    if schools(first)!=schools(second):return False
    # 대학명이 없으면 제목 첫머리의 같은 기관이 같은 사건의 주체여야 합니다.
    organization=subject_organization(first)
    if not schools(first) and (not organization or organization!=subject_organization(second)):return False
    # 숨긴 기사만 가진 지역·유형이 생기면 필터 결과가 사라집니다.
    if set(first.get('regions') or [])!=set(second.get('regions') or []):return False
    if not first.get('regions') or first.get('category')!=second.get('category'):return False
    if abs((datetime.fromisoformat(first['date'])-datetime.fromisoformat(second['date'])).total_seconds())>PRESS_WINDOW_HOURS*3600:return False
    if schools(first) and not same_story(first,second):return False
    if not schools(first) and story_actions(first['title'])!=story_actions(second['title']):return False
    # 모집 기사는 양쪽 모두 학년도가 명시되어야 같은 전형으로 봅니다.
    identities=[admission_identity(x) for x in (first,second)]
    if any(identities) and not all(i and i['year'] and not i['year_inferred'] for i in identities):return False
    a,b=normalize(first['title']),normalize(second['title'])
    words=lambda text:set(re.findall(NEW_FACT_WORDS,re.sub(r'\s+','',text)))
    if words(a)!=words(b):return False
    # 행사 예고와 결과 보도는 같은 행사라도 결과가 새 정보입니다.
    if {story_phase(a),story_phase(b)}=={'before','after'}:return False
    for pattern in (r'(20\d{2})',r'(\d+)회',r'(\d+)기',r'(\d+)차',r'(\d+)명',r'(\d+)건',r'(\d+)억',r'(\d+)만원',r'(\d+)%'):
        left,right=set(re.findall(pattern,a)),set(re.findall(pattern,b))
        if left and right and left!=right:return False
    terms_a,terms_b=distinctive_terms(first),distinctive_terms(second)
    shared=terms_a&terms_b
    if len(shared)<2 or len(shared)/max(1,min(len(terms_a),len(terms_b)))<.5:return False
    # 같은 기관명 뒤에 서로 다른 사업이 오면 양쪽 모두 고유어가 남습니다.
    if len(terms_a-shared)>=PRESS_DISTINCT_TAIL and len(terms_b-shared)>=PRESS_DISTINCT_TAIL:return False
    # 긴 제목에 다른 정보가 많으면 별도 관점이나 부분 중복일 수 있습니다.
    share=len(shared)/max(len(terms_a),len(terms_b))
    if share<PRESS_MIN_TITLE_SHARE:return False
    # 하루 넘게 떨어진 보도는 이어진 다른 활동일 수 있어 제목이 더 많이 같아야 합니다.
    gap=abs((datetime.fromisoformat(first['date'])-datetime.fromisoformat(second['date'])).total_seconds())/3600
    if gap>24 and share<PRESS_LONG_GAP_TITLE_SHARE:return False
    # 여러 소식을 '…'로 이어 붙인 제목은 단일 보도와 같은 기사가 아닙니다.
    digest=lambda title:len(re.findall(r'…|\.\.\.',title))>=2
    if digest(first['title'])!=digest(second['title']):return False
    body_a,body_b=informative_body(first),informative_body(second)
    if min(len(body_a),len(body_b))>=80 and SequenceMatcher(None,body_a,body_b,autojunk=False).ratio()<.5:return False
    return True


def press_partitions(rows):
    """모든 쌍이 조건을 만족하는 묶음만 만듭니다. 이어진 기사만으로 합치지 않습니다."""
    parts=[]
    for item in sorted(rows,key=quality,reverse=True):
        target=next((part for part in parts if all(press_same_story(item,other) for other in part)),None)
        if target is None:parts.append([item])
        else:target.append(item)
    return parts


def story_owner(item):
    """같은 사건을 비교할 주체: 대학명 집합, 대학명이 없으면 제목 첫머리 기관, 둘 다 없으면 일반 기사 묶음.

    일반 기사('대학만화웹툰대전 개최')도 같은 행사·사업 고유어를 공유하면 같은 사건으로 비교합니다.
    """
    schools=tuple(sorted(item.get('school_names') or []))
    if schools:return schools
    organization=subject_organization(item)
    return ('@'+organization,) if organization else GENERAL_OWNER



@lru_cache(maxsize=65536)
def title_regions(title):
    """제목에 나온 시·도. 시·군·구 이름은 한 시·도에만 있는 이름일 때만 씁니다('동구'처럼 여러 곳에 있는 이름은 뺍니다)."""
    found=set()
    for word in re.findall(r'[가-힣]{2,}',normalize(title)):
        # '광주'·'강원지사'처럼 시·도 이름으로 시작하면 시·도로만 봅니다(경기 광주시와 헷갈리지 않게).
        provinces={region for short,region in PROVINCE_SHORT.items() if word.startswith(short)}
        if provinces:
            found|=provinces;continue
        # '상주시장학회'·'가평'처럼 정식 이름(상주시)으로 시작하거나 접미어 없이 쓴 시·군·구입니다.
        for name,records in LOCALITIES.items():
            regions={record['region'] for record in records}
            if len(regions)==1 and (word.startswith(name) and len(name)>=3 or word in (name[:-1],) and len(word)>=2):
                found|=regions;break
    return frozenset(found)


def lead_subject(item):
    """제목 첫머리 주체('에어부산, …'의 '에어부산'). 머리표와 따옴표는 뺍니다."""
    title=re.sub(r'^\s*(?:\[[^\]]*\]|\([^)]*\))\s*','',normalize(item.get('title','')))
    match=re.match(r'([가-힣a-z0-9]{2,})',title)
    return match.group(1) if match else ''


def item_cached(function):
    """제목·대학명만으로 정해지는 기사별 계산을 한 번만 합니다. 기사 쌍마다 다시 계산하면 수집이 느려집니다."""
    cache={}
    def cached(item):
        key=(item.get('title',''),tuple(item.get('school_names') or []),item.get('school',''))
        if key not in cache:cache[key]=frozenset(function(item))
        return cache[key]
    cached.__doc__=function.__doc__
    return cached


def event_title(item):
    """' - 전체 행사 - SNU 캘린더 - 서울대 소식'처럼 여러 겹인 매체·사이트 꼬리표를 뗀 제목."""
    title=item.get('title','')
    for _ in range(4):
        title=re.sub(TITLE_SUFFIX,'',title)
    return title


@item_cached
def event_terms(item):
    return distinctive_terms(dict(item,title=event_title(item)))


@item_cached
def event_entities(item):
    """사건을 가리키는 고유어 후보: 3글자 이상 한글 명사·영문 약어. 흔한 대학 일반어와 서술어는 뺍니다.

    '위험사회 HUSS 사업단'처럼 행사 주체 조직의 이름은 같은 조직의 다른 활동에도 쓰이므로 근거가 아닙니다.
    다만 '○○대학원 신설'처럼 조직 자체가 소식이면 근거로 씁니다.
    """
    found=set()
    # '화성시'·'완주군' 같은 지자체 이름은 행사 장소라 같은 곳의 다른 행사에도 쓰입니다. 협약 상대일 때만 근거로 씁니다.
    agreement='agreement' in event_kinds(normalize(item['title']))
    for term in event_activity_terms(item):
        if re.search(r'\d',term) or term in EVENT_ENTITY_GENERIC or re.search(EVENT_ENTITY_ENDING,term):continue
        if term in PLACE_NAMES and not agreement:continue
        if len(re.sub(r'[^가-힣]','',term))>=3 or re.fullmatch(r'[a-z][a-z\-]+',term) and term not in EVENT_COMMON_LATIN:
            found.add(term)
    return found


@item_cached
def event_activity_terms(item):
    """제목 단어 중 행사 주체 조직의 이름 구간 밖에도 나오는 말. 조직 이름은 같은 조직의 다른 활동에도 쓰입니다."""
    title=normalize(event_title(item))
    # '충북아이돌봄센터, 아이돌봄 축제'의 '아이돌봄'은 조직 이름 밖에도 있으므로 남습니다.
    outside=title if 'opening' in event_kinds(title) else re.sub(EVENT_ORGANIZATION_SPAN,' ',title)
    outside=re.sub(r'[\W_]+','',outside)
    # '김철수 교수 연구팀'의 사람 이름은 조직명이 아닙니다.
    people=set(re.findall(r'([가-힣]{2,4})\s*(?:교수|총장|박사|학생|대학원생|연구원|씨|대표|회장|원장|소장|단장|센터장|팀장|작가|기자)',title))
    return {term for term in event_terms(item) if term in outside or term in people}


def entity_owner_counts(items):
    """고유어가 몇 개 주체(대학·기관)의 기사에 쓰였는지 셉니다. 여러 대학이 쓰는 말은 사건 근거가 아닙니다."""
    owners=defaultdict(set)
    for item in items:
        owner=story_owner(item)
        # 일반 기사는 여러 주제를 한데 모은 묶음이라, 넣으면 대학 기사 고유어가 흔한 말로 잘못 바뀝니다.
        if owner and owner!=GENERAL_OWNER:owners[owner].update(event_terms(item))
    joined=['\x00'+'\x00'.join(sorted(terms))+'\x00' for terms in owners.values()]
    @lru_cache(maxsize=None)
    def count(entity):
        return sum(entity in text for text in joined)
    return count


@lru_cache(maxsize=65536)
def event_kinds(title):
    compact=re.sub(r'\s+','',title)
    return frozenset(kind for kind,pattern in EVENT_KINDS if re.search(pattern,compact,re.I))


def event_phase(title):
    compact=re.sub(r'\s+','',normalize(title))
    # 참여 인원이 나온 행사 보도는 결과 보도이고, 'N일 개최/개막'은 예고입니다.
    if re.search(PHASE_AFTER,compact) or re.search(r'\d+명(?:이|여명)?(?:참여|참가|몰려|모여|찾아)',compact):return 'after'
    if re.search(PHASE_BEFORE,compact) or re.search(r'\d+일(?:까지)?(?:개최|개막|연다|열린다|진행한다|설명회)',compact):return 'before'
    return ''


@lru_cache(maxsize=65536)
def incidents(title):
    """제목이 알리는 돌발 사건의 갈래. '사고 위험'·'의료 붕괴 위기'는 사건 발생이 아니라 위험 이야기라 뺍니다.

    '체포'와 '입건'처럼 같은 갈래의 낱말은 같은 사건을 다르게 쓴 것입니다.
    """
    plain=re.sub(r'[‘\'“"「『][^’\'”"」』]{1,40}[’\'”"」』]',' ',title)
    found=re.findall(r'(?<![가-힣])('+'|'.join(w for words in EVENT_INCIDENT_FAMILIES.values() for w in words)+
                     r')(?!\s*(?:위험|위기|예방|방지|대비|우려|대응\s*훈련))',plain)
    return frozenset(family for family,words in EVENT_INCIDENT_FAMILIES.items() if set(found)&set(words))


@lru_cache(maxsize=65536)
def named_people(title):
    """'김교흥 의원'·'이만승·윤철호 교수'처럼 직함 앞에 붙은 2~3글자 이름. '부산대 교수'의 대학명은 뺍니다."""
    names=set()
    for listed in re.findall(r'(?<![가-힣])([가-힣]{2,3}(?:\s*[·‧ㆍ,]\s*[가-힣]{2,3})*)\s*'+PERSON_TITLE,normalize(title)):
        names.update(re.split(r'\s*[·‧ㆍ,]\s*',listed))
    # '석좌 교수'·'차기 회장'·'과기부 장관'·'인천시 교육감'의 앞말은 직함 수식어나 기관·지역명입니다.
    return frozenset(n for n in names if not n.endswith(('대','부','청','처','원','시','도')) and n not in PERSON_TITLE_MODIFIERS and not PATTERN.fullmatch(n))


def event_numbers(title):
    """제목 숫자를 비교하기 쉽게 바꿉니다. '5천108명'은 '5108명'과 같은 수입니다."""
    title=re.sub(r'(\d+)천\s*(\d{3})(?!\d)',r'\1\2',normalize(title))
    return {pattern:set(re.findall(pattern,title)) for pattern in EVENT_NUMBER_PATTERNS}


def event_conflicts(first,second,shared):
    """두 기사가 서로 다른 사건이라는 근거 목록. 비어 있으면 충돌이 없습니다."""
    a,b=normalize(first['title']),normalize(second['title'])
    blocked=[]
    # 한쪽 병원명이 다른 쪽에 포함되면('강원대병원' ⊂ '강원대병원·행동발달증진센터') 같은 병원입니다.
    hospitals_a,hospitals_b=hospital_names(first['title']),hospital_names(second['title'])
    if hospitals_a and hospitals_b and not hospitals_a&hospitals_b:blocked.append('different hospitals')
    identities=[admission_identity(x) for x in (first,second)]
    if admission_match(first,second) is False or any(identities) and not all(i and i['year'] and not i['year_inferred'] for i in identities):
        blocked.append('admission identity uncertain')
    campus_map=lambda n:{u['name']:set(u.get('campus_names',[])) for u in n.get('universities',[]) if u.get('campus_status') in ('matched','region_only') and u.get('campus_names')}
    campus_a,campus_b=campus_map(first),campus_map(second)
    if any(not campus_a[name]&campus_b[name] for name in campus_a.keys()&campus_b.keys()):blocked.append('different campuses')
    # 공백을 지우면 '박사 과정'이 '사과'로 읽히므로 단어 첫머리에서만 찾습니다. '2차 사고'의 '2차'는 후속 단계가 아닙니다.
    words=lambda text:set(re.findall(r'(?<![가-힣])(?:'+NEW_FACT_WORDS+r')(?<!2차)|(?<![가-힣])2차(?!\s*(?:사고|피해|감염|가해|전지))',text))
    if words(a)!=words(b):blocked.append('new-fact word differs')
    # 부상·사고·체포 같은 돌발 사건은 관련 행사 보도와 별개의 사실입니다. 따옴표 안의 곡명·행사명은 보지 않습니다.
    if incidents(a)!=incidents(b):blocked.append('incident reported on one side only')
    if {event_phase(first['title']),event_phase(second['title'])}=={'before','after'}:blocked.append('announcement vs result')
    # 한쪽 숫자가 다른 쪽에 모두 들어 있으면('2위' ⊂ '2위·득점 3위') 세부 정보 차이일 뿐입니다.
    numbers_a,numbers_b=event_numbers(first['title']),event_numbers(second['title'])
    if any(numbers_a[p] and numbers_b[p] and not (numbers_a[p]<=numbers_b[p] or numbers_b[p]<=numbers_a[p]) for p in EVENT_NUMBER_PATTERNS):
        blocked.append('conflicting numbers')
    kinds_a,kinds_b=event_kinds(first['title']),event_kinds(second['title'])
    if kinds_a and kinds_b and not kinds_a&kinds_b:blocked.append('different event types')
    # 한쪽 인물이 다른 쪽 제목 어디에든 나오면 같은 인물입니다('김인회 인하대 로스쿨 교수'의 '로스쿨'은 이름이 아닙니다).
    people_a,people_b=named_people(first['title']),named_people(second['title'])
    if people_a and people_b and not people_a&people_b and not any(n in b for n in people_a) and not any(n in a for n in people_b):
        blocked.append('different people')
    # 따옴표 안이 행사·과정 이름일 때만 비교합니다. 인용한 발언("…이끈다")은 매체마다 다르게 고릅니다.
    # 따옴표 안이 축제·포럼 같은 행사 이름일 때만 비교합니다. '괴물 양자컴'·'15년 벽'처럼 매체가 고른 표현은 다를 수 있습니다.
    quoted=lambda title:{re.sub(r'\W','',s) for s in re.findall(r'[‘\'“"「『]([^’\'”"」』]{2,40})[’\'”"」』]',title)
                         if re.search(EVENT_NAME_WORDS,s) and len(s.split())<=6}
    compact_a,compact_b=re.sub(r'\W','',a),re.sub(r'\W','',b)
    qa,qb=quoted(a),quoted(b)
    if qa and qb and not any(q in compact_b for q in qa) and not any(q in compact_a for q in qb):blocked.append('different quoted titles')
    # 원문 요약이 있으면 요약에도 같은 고유어가 나와야 합니다.
    if shared:
        for item in (first,second):
            body=informative_body(item)
            if len(body)>=80 and not any(e in body for e in shared):blocked.append('summary lacks shared entity');break
    return blocked



def shared_core(x,y):
    """두 고유어가 같은 대상을 가리키면 공통 부분을 돌려줍니다.

    '킥보드'와 '전동킥보드'처럼 한쪽이 다른 쪽을 포함하거나,
    '양자컴퓨터'와 '양자컴퓨팅'처럼 앞 세 글자 이상이 같으면 같은 고유어로 봅니다.
    """
    if x in y or y in x:return x if len(x)<=len(y) else y
    prefix=0
    while prefix<min(len(x),len(y)) and x[prefix]==y[prefix]:prefix+=1
    core=x[:prefix]
    return core if len(re.sub(r'[^가-힣]','',core))>=3 else ''


@lru_cache(maxsize=65536)
def title_shape(title):
    """같은 사건 비교에서 제외하거나 따로 다룰 제목 형태. 제목만으로 정해져 기사 쌍마다 다시 계산하지 않습니다."""
    # 칼럼·소식 모음·사진 기사는 비교하지 않습니다.
    digest=len(re.findall(r'…|\.\.\.',title))>=2 or bool(re.search(r'\[(?:포토|사진|사진뉴스|PHOTO)',title,re.I))
    # '학정포럼 개최·기획초대전 진행'처럼 동작을 가운뎃점·쉼표로 이어 붙인 제목은 두 소식을 묶은 기사입니다.
    # '개최…논문 610건 발표'의 말줄임표 뒤는 같은 소식의 세부 내용입니다.
    verbs=r'(?:개최|진행|체결|선정|수상|성료|운영|출범|발표|실시)'
    multi_story=bool(re.search(verbs+r'\s*[·ㆍ,]\s*\S.*'+verbs,event_title(dict(title=title))))
    # '윤경(인하대)'처럼 괄호 안에만 나온 대학은 기사 주체가 아니므로 다른 관점의 기사일 수 있습니다.
    side_mention=bool(PATTERN.search(title)) and not PATTERN.search(re.sub(r'\([^)]*\)','',title))
    return dict(excluded=automatic_merge_exclusion(dict(title=title)) or digest,multi_story=multi_story,side_mention=side_mention)


def event_pair(first,second,owner_count,topic_count=lambda owner,entity:0):
    """두 기사가 같은 사건인지 판정합니다. (판정, 근거)

    merge: 같은 사건 / candidate: 같은 사건 근거가 있으나 막는 조건이 있음(검토 후보)
    weak: 같은 사건이라는 근거도, 다르다는 근거도 부족함 / conflict: 근거는 부족하고 다르다는 근거가 있음
    None: 대학·기간·소식 모음 등 비교 대상이 아님
    """
    shape_a,shape_b=title_shape(first.get('title','')),title_shape(second.get('title',''))
    if shape_a['excluded'] or shape_b['excluded']:return None,{}
    if shape_a['multi_story']!=shape_b['multi_story']:return None,{}
    try:
        gap=abs((datetime.fromisoformat(first['date'])-datetime.fromisoformat(second['date'])).total_seconds())/3600
    except (TypeError,ValueError,KeyError):return None,{}
    if gap>PRESS_WINDOW_HOURS:return None,{}
    owner=story_owner(first)
    if not owner or owner!=story_owner(second):return None,{}
    if shape_a['side_mention'] or shape_b['side_mention']:return None,{}
    entities_a,entities_b=event_entities(first),event_entities(second)
    terms_a,terms_b=event_activity_terms(first),event_activity_terms(second)
    # '킥보드'와 '전동킥보드'처럼 한쪽이 다른 쪽을 포함하면 같은 고유어로 봅니다.
    shared=set()
    for x in entities_a:
        for y in entities_b:
            core=shared_core(x,y)
            if core and owner_count(core)<=EVENT_ENTITY_MAX_OWNERS:shared.add(core)
    # 고유어 하나에 더해 겹치는 말은 '글로벌'·'미래'처럼 여러 대학이 쓰는 말이 아니거나, 같은 행사 유형이어야 합니다.
    kinds_shared=event_kinds(first['title'])&event_kinds(second['title'])
    others={t for t in terms_a&terms_b if not any(e in t for e in shared)
            and (owner_count(t)<=EVENT_SUPPORT_MAX_OWNERS or event_kinds(t))}|kinds_shared
    evidence=dict(shared_entities=sorted(shared),shared_terms=sorted(others),gap_hours=round(gap,1))
    # 충돌 검사는 근거가 약한 쌍에도 합니다. 같은 묶음에 들어갈 때 다른 기사와 충돌하지 않는지 봐야 하기 때문입니다.
    blocked=event_conflicts(first,second,shared)
    # 고유어가 없거나 하나만 겹치고 나머지가 다르면 판단할 근거가 부족한 쌍(weak)입니다. 후보로도 올리지 않습니다.
    named_event=False
    if owner==GENERAL_OWNER:
        # 일반 기사는 지자체만 다른 같은 종류 행사(농업인대학 졸업식, 입시설명회)가 많습니다.
        regions_a,regions_b=title_regions(first['title']),title_regions(second['title'])
        if regions_a and regions_b and not regions_a&regions_b:blocked.append('different places')
        # 고유어 하나로 묶으려면 한쪽 표기가 다섯 글자 이상의 이름('대학만화웹툰대전'과 '웹툰대전')이거나
        # 제목 첫머리 주체·지역이 같아야 합니다.
        # 한쪽이 다른 쪽을 그대로 포함하고, 공통 부분이 네 글자 이상이며 실제로 두 글자 이상 긴 이름일 때만 봅니다.
        # ('한국대학신문'과 '한국대학바둑연맹'의 앞부분, '이탈리아'와 '이탈리아서'의 조사는 해당하지 않습니다.)
        long_name=any(len(core)>=4 and (x in y or y in x) and (len(core)>=5 or max(len(x),len(y))-len(core)>=2)
                      for x in entities_a for y in entities_b for core in [shared_core(x,y)] if core in shared)
        if len(shared)<2 and not long_name and lead_subject(first)!=lead_subject(second) and not regions_a&regions_b:
            return ('conflict',dict(evidence,blocked_by=', '.join(blocked))) if blocked else ('weak',evidence)
        # 긴 행사·사업명('대학만화웹툰대전')은 그 자체로 같은 주제의 근거입니다.
        named_event=long_name
    if not shared or not (len(shared)>=2 or others or named_event):
        return ('conflict',dict(evidence,blocked_by=', '.join(blocked))) if blocked else ('weak',evidence)
    if gap>48 and len(shared)<2:blocked.insert(0,'over 48h apart with one entity')
    # 하루 넘게 떨어진 보도는 같은 주제의 다른 활동일 수 있어 고유어 외의 공통어도 있어야 합니다.
    elif gap>24 and not others:blocked.insert(0,'over 24h apart without supporting words')
    # '국립의대'처럼 한 대학의 기사 여러 건에 걸친 말은 사건이 아니라 주제입니다.
    # 주제어만 겹치면 고유어 밖의 공통어가 둘 이상이거나, 하루 안의 같은 행사 유형에 공통어가 하나 이상 있어야 합니다.
    topical=[e for e in shared if topic_count(owner,e)>=EVENT_TOPIC_MIN_ARTICLES]
    support=others-kinds_shared
    if topical and len(shared)==len(topical) and not (len(support)>=2 or kinds_shared and gap<=24 and support):
        blocked.insert(0,'shared word is an ongoing topic of this university')
    if blocked:return 'candidate',dict(evidence,blocked_by=', '.join(blocked))
    return 'merge',evidence


def event_story_groups(items,groups):
    """기존 묶음과 단독 기사를 단위로, 같은 주체·72시간 안의 같은 사건을 묶습니다.

    새 단위는 묶음 대표 단위와 같은 사건(merge)이고, 묶음의 다른 기사 절반 이상과 같은 사건이며,
    어느 기사와도 다르다는 높은 위험 근거(인물·숫자·단계·돌발 사건 등)나 비교 제외(None)가 없을 때만 들어갑니다.
    '성균관대, 유지범 총장 연임'처럼 짧아서 일부 기사와 비교 근거가 부족한(weak) 보도도 이렇게 묶입니다.
    막힌 쌍은 검토 후보로만 남깁니다.
    """
    by_id={x['id']:x for x in items}
    unit_of={}
    units=[]
    for group in groups:
        units.append(dict(ids=list(group['article_ids']),group=group))
        for i in group['article_ids']:unit_of[i]=len(units)-1
    for item in items:
        if item['id'] not in unit_of:
            unit_of[item['id']]=len(units);units.append(dict(ids=[item['id']],group=None))
    owner_count=entity_owner_counts(items)
    owner_entities=defaultdict(list)
    for item in items:
        try:day=(datetime.fromisoformat(item['date'])+timedelta(hours=9)).date()
        except (TypeError,ValueError,KeyError):continue
        owner_entities[story_owner(item)].append((day,event_entities(item)))
    # 같은 보도가 하루에 몰린 것과 달리, 여러 날에 걸쳐 나온 말은 진행 중인 주제입니다.
    @lru_cache(maxsize=None)
    def topic_count(owner,entity):
        return len({day for day,entities in owner_entities[owner] if any(entity in e for e in entities)})
    buckets=defaultdict(list)
    for index,unit in enumerate(units):
        owners={story_owner(by_id[i]) for i in unit['ids']}
        if len(owners)==1 and None not in owners:buckets[owners.pop()].append(index)
    merged,candidates=[],[]
    pair_cache={}
    def pair(x,y):
        key=(x,y) if x<y else (y,x)
        if key not in pair_cache:pair_cache[key]=event_pair(by_id[x],by_id[y],owner_count,topic_count)
        return pair_cache[key]
    for indexes in buckets.values():
        if len(indexes)<2:continue
        rank=lambda index:max(quality(by_id[i]) for i in units[index]['ids'])
        parts=[]
        for index in sorted(indexes,key=rank,reverse=True):
            def joins(part):
                cross=[pair(x,y) for other in part for x in units[index]['ids'] for y in units[other]['ids']]
                # 시간 차·주제어·인용구 차이는 근거 부족일 뿐이고, 인물·숫자·단계 등 높은 위험 사유만 다른 사건의 근거입니다.
                if any(decision is None or decision in ('candidate','conflict') and candidate_merge_risk(evidence['blocked_by'])=='high'
                       for decision,evidence in cross):return False
                cross=[decision for decision,_ in cross]
                # part[0]은 정보량이 가장 많은 대표 단위입니다.
                if any(pair(x,y)[0]!='merge' for x in units[index]['ids'] for y in units[part[0]]['ids']):return False
                return cross.count('merge')*2>=len(cross)
            target=next((part for part in parts if joins(part)),None)
            if target is None:parts.append([index])
            else:target.append(index)
        # 같은 주제 묶음: 사건 묶음끼리 대표 기사가 같은 사건이거나 중간 위험 후보이고,
        # 두 묶음의 어떤 기사 사이에도 다른 사건이라는 높은 위험 근거나 비교 제외(소식 모음 등)가 없으며,
        # 합친 묶음의 기간이 72시간 안이면 하나로 보여 줍니다.
        def best(part):return max((i for index in part for i in units[index]['ids']),key=lambda i:quality(by_id[i]))
        def topic_joins(left,right):
            decision,evidence=pair(best(left),best(right))
            if decision not in ('merge','candidate') or decision=='candidate' and candidate_merge_risk(evidence['blocked_by'])=='high':return False
            ids=[i for index in left+right for i in units[index]['ids']]
            dates=[datetime.fromisoformat(by_id[i]['date']) for i in ids]
            if (max(dates)-min(dates)).total_seconds()>PRESS_WINDOW_HOURS*3600:return False
            return not any(cross is None or cross in ('candidate','conflict') and candidate_merge_risk(detail['blocked_by'])=='high'
                           for a in left for b in right for x in units[a]['ids'] for y in units[b]['ids'] for cross,detail in [pair(x,y)])
        topic=[False]*len(parts)
        joined=True
        while joined:
            joined=False
            for first in range(len(parts)):
                for second in range(first+1,len(parts)):
                    if parts[first] and parts[second] and topic_joins(parts[first],parts[second]):
                        parts[first]=parts[first]+parts[second];parts[second]=[];topic[first]=joined=True
            topic=[flag for flag,part in zip(topic,parts) if part]
            parts=[part for part in parts if part]
        part_of={index:n for n,part in enumerate(parts) for index in part}
        for part,by_topic in zip(parts,topic):
            if len(part)<2:continue
            ids=sorted(i for index in part for i in units[index]['ids'])
            members=[by_id[i] for i in ids]
            representative=max(members,key=quality)
            evidence=[pair(x,y)[1] for n,a in enumerate(part) for b in part[n+1:]
                      for x in units[a]['ids'][:1] for y in units[b]['ids'][:1]]
            merged.append(dict(version=7,representative_id=representative['id'],article_ids=ids,
                               basis='same topic across event groups' if by_topic else 'same event entities across different titles',
                               evidence=dict(shared_entities=sorted({e for x in evidence for e in x.get('shared_entities',[])}),
                                             shared_terms=sorted({e for x in evidence for e in x.get('shared_terms',[])}),
                                             max_gap_hours=max(x.get('gap_hours',0) for x in evidence),
                                             merged_groups=[units[index]['group']['version'] for index in part if units[index]['group']],
                                             checks='same owner, within 72h, shared rare entities and action, no stage/number/event-type/quote/summary conflict'),
                               representative_reason=representative_reason(representative,members)))
        # 막힌 쌍은 서로 다른 최종 묶음에 있을 때만 검토 후보로 남깁니다.
        reps={index:max(units[index]['ids'],key=lambda i:quality(by_id[i])) for index in indexes}
        for n,a in enumerate(indexes):
            for b in indexes[n+1:]:
                if part_of[a]==part_of[b]:continue
                decision,evidence=pair(reps[a],reps[b])
                if decision in ('candidate','merge'):
                    blocked_by=evidence.get('blocked_by','not every member pair matches')
                    candidates.append(dict(representative_id=reps[a],article_ids=sorted([reps[a],reps[b]]),
                                           decision='candidate_only',reason='event entities overlap but identity is not certain',
                                           merge_risk=candidate_merge_risk(blocked_by),evidence=dict(evidence,blocked_by=blocked_by)))
    absorbed={id(units[i]['group']) for g in merged for i in {unit_of[x] for x in g['article_ids']} if units[i]['group']}
    kept=[g for g in groups if id(g) not in absorbed]
    return kept+merged,candidates


def candidate_merge_risk(blocked_by):
    """검토 후보를 합쳤을 때 다른 사건을 잘못 묶을 위험. 후보는 위험도와 상관없이 자동으로 합치지 않습니다.

    high: 인물·단계·숫자·돌발 사건 등 서로 다른 사건이라는 근거가 있음
    medium: 주제어·인용 제목·시간 차처럼 판단이 애매함
    low: 두 기사는 같은 사건으로 보이나 묶음의 다른 기사와 조건이 맞지 않음
    """
    reasons=set(blocked_by.split(', '))
    if reasons&CANDIDATE_HIGH_RISK:return 'high'
    if reasons<={'not every member pair matches'}:return 'low'
    return 'medium'


def representative_reason(representative,members):
    has_body,body_words,_,title_words,_,original,_,_=quality(representative)
    first=f'RSS 요약 정보량 최다(고유어 {body_words}개)' if has_body else '요약 있는 기사 없음 → 제목 구체성 기준'
    return f'{len(members)}건 중 {first} · 제목 단어 {title_words}개' + (' · 원문 링크 있음' if original else '')


def duplicate_review_groups(items,story_groups=None,event_candidates=None):
    if story_groups is None:story_groups,event_candidates=public_story_groups(items,with_candidates=True)
    by_id={x['id']:x for x in items}
    group_of={i:n for n,group in enumerate(story_groups) for i in group['article_ids']}
    # 이미 한 묶음으로 공개된 기사끼리는 다시 검토 후보로 올리지 않습니다.
    settled=lambda ids:len({group_of.get(i,('single',i)) for i in ids})==1
    groups=[]
    for row in deduplicate(items):
        if row['duplicate_count']<2:continue
        members=[by_id[i] for i in row['duplicate_ids'] if i in by_id]
        if len(press_partitions(members))==1 or all(confirmed_same_story(by_id[row['id']],m) for m in members if m['id']!=row['id']):continue
        if settled(row['duplicate_ids']):continue
        groups.append(dict(representative_id=row['id'],article_ids=row['duplicate_ids'],
                           decision='candidate_only',reason='event similarity is not identity',merge_risk='medium'))
    listed={tuple(sorted(g['article_ids'])) for g in groups}
    groups.extend(c for c in event_candidates or [] if not settled(c['article_ids']) and tuple(c['article_ids']) not in listed)
    return groups


def public_story_groups(items,with_candidates=False):
    groups=[dict(version=4,representative_id=row['id'],article_ids=row['duplicate_ids'],
                 basis='identical complete visible content and links')
            for row in confirmed_deduplicate(items) if row['duplicate_count']>1]
    claimed={i for group in groups for i in group['article_ids']}
    # 다른 링크로 들어온 같은 제목의 기사(재수집·언론사 RSS와 포털 동시 수집 등)를 먼저 묶습니다.
    titled=defaultdict(list)
    for item in items:
        key=title_identity(item)
        if key and item['id'] not in claimed:titled[key].append(item)
    for rows in titled.values():
        for part in identical_title_partitions(rows) if len(rows)>1 else []:
            if len(part)<2:continue
            groups.append(dict(version=6,representative_id=max(part,key=quality)['id'],article_ids=sorted(x['id'] for x in part),
                               basis='identical title'))
            claimed|={x['id'] for x in part}
    by_id={x['id']:x for x in items}
    for row in deduplicate(items):
        if row['duplicate_count']<2:continue
        # 대학명이 없는 기사는 아래에서 같은 주체 기관끼리 따로 비교합니다.
        members=[by_id[i] for i in row['duplicate_ids'] if i in by_id and i not in claimed and by_id[i].get('school_names')]
        for part in press_partitions(members):
            if len(part)<2:continue
            groups.append(dict(version=5,representative_id=max(part,key=quality)['id'],article_ids=sorted(x['id'] for x in part),
                               basis='same event across publishers'))
    # 대학명이 없는 기사는 같은 주체 기관·지역끼리만 비교합니다.
    claimed={i for group in groups for i in group['article_ids']}
    buckets=defaultdict(list)
    for item in items:
        organization=subject_organization(item)
        if item['id'] in claimed or item.get('school_names') or not organization or not item.get('regions'):continue
        buckets[(organization,tuple(sorted(item['regions'])))].append(item)
    for rows in buckets.values():
        for part in press_partitions(rows) if len(rows)>1 else []:
            if len(part)<2:continue
            groups.append(dict(version=5,representative_id=max(part,key=quality)['id'],article_ids=sorted(x['id'] for x in part),
                               basis='same event and institution without a university name'))
    groups,candidates=event_story_groups(items,groups)
    for group in groups:
        if 'representative_reason' not in group:
            members=[by_id[i] for i in group['article_ids']]
            group['representative_reason']=representative_reason(by_id[group['representative_id']],members)
    return (groups,candidates) if with_candidates else groups
