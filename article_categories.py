"""제목을 우선하며 입시와 일반 행사 참가자 모집을 구별합니다."""
import re

ADMISSIONS=re.compile(r'입시|신입생|편입|입학(?:전형|원서|지원|모집|설명회|상담)|(?<![가-힣])대입(?!구)|(?<![가-힣])(?:수시|정시)(?=$|[^가-힣]|모집|전형|지원|접수|일정|비율)')
SCHOLARSHIP=re.compile(r'장학|지원금|학자금|등록금\s*(?:지원|감면)')
EVENTS=re.compile(r'행사|특강|강연|축제|포럼|세미나|박람회|워크숍|학술대회|경진대회|공모전|시상식|컨퍼런스|졸업식|수료식|체험|캠프|콜로키움|공연|콘서트|음악회|연수')
RESEARCH=re.compile(r'연구|논문|특허|기술이전|기술사업화|학술상|구연상')

def classify_category(title,summary=''):
    for text in (title,summary):
        for pattern,category in ((ADMISSIONS,'입시·모집'),(SCHOLARSHIP,'장학·지원'),
                                 (EVENTS,'행사·특강'),(RESEARCH,'연구·성과')):
            if pattern.search(text):return category
    return '대학 소식'
