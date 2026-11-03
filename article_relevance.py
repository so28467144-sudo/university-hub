"""대학 소식과 부속 병원 자체 소식의 구분. 기사를 지우지 않고 공개 목록 표시 여부만 정합니다."""
import re
from named_affiliations import extract_facilities
from university_regions import PATTERN, select_alias_name, normalize_university_text

# 수의과대학 부설 동물병원은 교육시설이므로 부속 병원으로 보지 않습니다.
HOSPITAL_SUFFIX = r'\s*(?:학교)?\s*(?:부[속설]\s*)?(?![가-힣]{0,4}동물병원)[가-힣]{0,6}(?:병원|의료원)'
# 연구·학술·교육 성과는 대학 소식입니다.
ACADEMIC = (r'연구|논문|학술|학회|규명|개발|특허|게재|저널|NEJM|임상시험|의과대학|의대|의학과|간호대|간호학과|'
            r'학생|실습|교육(?!청|지원청)|수련|강의|산학|공동연구|심포지엄|국책과제|연구비|교수팀|연구팀|분석|예측\s*모델|지침|가이드라인|'
            r'혁신기술|기술이전|사업화|실험실|BRIC|한빛사|피인용|(?:구연|연제|초록|논문|학술|연구자|의학)상')
# 진료·수술·평가·인사·행사 같은 병원 운영 소식입니다.
OPERATIONS = (r'진료|수술|시술|치료|환자|환우|병동|병상|응급|외래|적정성|의료질|등급|인증|병원장|의료원장|원장|'
              r'취임|임명|선임|인사|부고|개원|개소|가동|오픈|기념식|캠페인|건강강좌|강좌|봉사|헌혈|기부|기탁|후원|간호사|'
              r'직원|표창|감사패|\d+\s*례|돌파|달성|시연|평가\s*결과|평가서|도입|행사|의\s*날')


def hospital_subject(title):
    """제목이 대학 자체가 아니라 부속 병원·의료원을 주체로 다루는지 확인합니다."""
    text = normalize_university_text(title)
    rest, facilities = extract_facilities(text)
    hospital = bool(facilities)
    plain_university = False
    for match in PATTERN.finditer(rest):
        if not select_alias_name(match, rest):
            continue
        if re.match(HOSPITAL_SUFFIX, rest[match.end():]):
            hospital = True
        else:
            plain_university = True
    return hospital and not plain_university


def classify_relevance(item):
    """(relevance, reason). 불확실하면 숨기지 않고 review로 남깁니다."""
    title = item.get('title', '')
    if not hospital_subject(title):
        return 'university', ''
    academic = re.search(ACADEMIC, title)
    operations = re.search(OPERATIONS, title)
    if operations and not academic:
        return 'hospital_excluded', f'부속 병원 운영 소식({operations.group()})'
    if academic and not operations:
        return 'university', f'부속 병원의 연구·교육 소식({academic.group()})'
    if academic and operations:
        return 'review', f'연구·교육({academic.group()})과 병원 운영({operations.group()}) 신호가 함께 있음'
    return 'review', '부속 병원 기사지만 대학 관련성을 판단할 신호가 없음'


def annotate_relevance(rows):
    """공개 기사에 판단 결과를 기록합니다. 다른 필드는 바꾸지 않습니다."""
    for row in rows:
        row['relevance'], row['relevance_reason'] = classify_relevance(row)
    return rows


def listed(rows):
    return [row for row in rows if row.get('relevance') != 'hospital_excluded']
