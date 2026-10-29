"""대학 본교와 소재지가 다른 부속기관. 주소는 공식 안내에서 확인한 것만 저장합니다."""
import re

FACILITIES=[
    dict(name='가천대 길병원',school='가천대학교',aliases=['가천대길병원','가천대학교길병원'],
         region='인천',address='',source='https://www.ichealthedu.kr/main/page.jsp?code=intro_gil'),
    dict(name='강동경희대학교병원',school='경희대학교',aliases=['강동경희대학교병원','강동경희대병원'],
         region='서울',address='서울특별시 강동구 동남로 892',source='https://www.khnmc.or.kr/en/document-download.do?name=Brochures_Korean.pdf'),
    dict(name='세종충남대학교병원',school='충남대학교',aliases=['세종충남대학교병원','세종충남대병원'],
         region='세종',address='',source='https://www.cnush.co.kr/'),
    dict(name='분당서울대학교병원',school='서울대학교',aliases=['분당서울대학교병원','분당서울대병원'],
         region='경기도',address='경기도 성남시 분당구 구미로173번길 82',source='https://www.snubh.org/index.do'),
    dict(name='화순전남대학교병원',school='전남대학교',aliases=['화순전남대학교병원','화순전남대병원'],
         region='전남',address='전라남도 화순군 화순읍 서양로 322',source='https://www.cnuhh.com/cnuhh/main.cs'),
    dict(name='칠곡경북대학교병원',school='경북대학교',aliases=['칠곡경북대학교병원','칠곡경북대병원'],
         region='대구',address='대구광역시 북구 호국로 807',source='https://www.knuch.kr/content/down/병원생활%20안내문_2025.pdf'),
    dict(name='양산부산대학교병원',school='부산대학교',aliases=['양산부산대학교병원','양산부산대병원'],
         region='경남',address='경상남도 양산시 물금읍 금오로 20',source='https://www.medicalkorea.or.kr/kmtp/kntp/about/hospitalDetail.do?hspCd=OPNUY'),
]

def extract_facilities(text):
    matches=[]
    spans=[]
    for record in FACILITIES:
        for alias in record['aliases']:
            for match in re.finditer(r'\s*'.join(map(re.escape,alias)),text):
                spans.append(match.span())
                if record not in matches:matches.append(record)
    for start,end in sorted(set(spans),reverse=True):text=text[:start]+' '*(end-start)+text[end:]
    return text,matches
