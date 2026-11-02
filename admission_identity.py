"""Conservative graduate admission identities, independent of publisher wording."""
import re
import unicodedata
from datetime import datetime


def admission_identity(item):
    title=unicodedata.normalize('NFKC',item['title'])
    title=re.sub(r'(?<=\d),(?=\d{3}(?:\D|$))','',title)
    compact=re.sub(r'\s+','',title)
    if '대학원' not in compact or not re.search(r'신입생|신입학|석사.*모집|박사.*모집',compact) or not re.search(r'모집|접수',compact):
        return None
    schools=set(item.get('school_names') or item.get('school','').split(' · ')) - {'','대학 일반','대학명 미확인'}
    if len(schools)!=1:return None
    year_match=re.search(r'(20\d{2})학년도',compact)
    term='first' if re.search(r'전기|전반기|1학기',compact) else 'second' if re.search(r'후기|후반기|2학기',compact) else ''
    year=year_match.group(1) if year_match else ''
    inferred=False
    if not year and term:
        try:
            date=datetime.fromisoformat(item.get('date',''))
            if term=='first' and date.month>=8:year=str(date.year+1);inferred=True
            elif term=='second' and 2<=date.month<=8:year=str(date.year);inferred=True
        except ValueError:pass
    units=tuple(sorted(set(re.findall(r'(일반|교육|경영|보건|행정|법무|정보통신|산업|군사|국방|의료|상담|문화|간호|예술|언론홍보|사회복지|국제정보보호|통역번역|융합과학|도시과학|정책과학)대학원',compact))))
    degree=tuple(sorted(set(re.findall(r'석사|박사|신편입|편입',compact))))
    departments=tuple(sorted(set(re.findall(r'[가-힣A-Za-z]{2,20}(?:학과|학부|전공)',title))))
    rounds=tuple(sorted(set(re.findall(r'\d+차|제\d+기',compact))))
    phase=tuple(sorted(set(re.findall(r'추가모집|재모집|마감|합격|결과발표|설명회|접수시작|취소|연기',compact))))
    quotas=tuple(sorted(set(re.findall(r'(\d[\d,]*)명(?:을)?(?:모집|선발)',compact))))
    deadlines=tuple(sorted(set(re.findall(r'(\d{1,2})일(?:까지|마감)',compact))))
    return dict(school=next(iter(schools)),year=year,year_inferred=inferred,term=term,
                units=units,degree=degree,departments=departments,rounds=rounds,phase=phase,quotas=quotas,deadlines=deadlines)


def admission_match(first,second):
    """None: ordinary stories; False: protect distinct/underspecified campaigns."""
    a,b=admission_identity(first),admission_identity(second)
    if not a and not b:return None
    if not a or not b:return False
    if any(a[k]!=b[k] for k in ('school','units','degree','departments','rounds','phase')):return False
    for key in ('year','term','quotas','deadlines'):
        if a[key] and b[key] and a[key]!=b[key]:return False
    # No year identity means no semantic admission merge. Never infer an entire
    # missing campaign from '대학원 신입생 모집' alone.
    if not a['year'] or not b['year']:return None
    return True


def admission_bucket(item):
    a=admission_identity(item)
    if not a or not a['year']:return ''
    return '@admission:'+repr((a['school'],a['year'],a['units'],a['degree'],a['phase']))
