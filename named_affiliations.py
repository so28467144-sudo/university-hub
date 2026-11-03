"""대학 본교와 소재지가 다른 부속기관. 주소는 공식 안내에서 확인한 것만 저장합니다."""
import re

FACILITIES=[
    dict(name='고려대학교안산병원',school='고려대학교',aliases=['고려대학교안산병원','고려대안산병원','고대안산병원'],
         region='경기도',address='경기도 안산시 단원구 적금로 123',source='https://health.kumc.or.kr/center/directions.do'),
    dict(name='고려대학교안암병원',school='고려대학교',aliases=['고려대학교안암병원','고려대안암병원','고대안암병원'],
         region='서울',address='서울특별시 성북구 고려대로 73',source='https://centerforesg.kumc.or.kr/downloadFile.do?attachNo=15101'),
    dict(name='중앙대학교광명병원',school='중앙대학교',aliases=['중앙대학교광명병원','중앙대광명병원'],
         region='경기도',address='경기도 광명시 덕안로 110',source='https://www.cauhs.or.kr/'),
    dict(name='중앙대학교병원',school='중앙대학교',aliases=['중앙대학교병원','중앙대병원'],
         region='서울',address='서울특별시 동작구 흑석로 102',source='https://ch.cauhs.or.kr/ghealth/conts/103002001000000.do'),
    dict(name='전남대학교병원',school='전남대학교',aliases=['전남대학교병원','전남대병원'],
         region='광주',address='광주광역시 동구 제봉로 42',source='https://www.cnuh.com/ccrc/sub.cs?m=19'),
    dict(name='한양대학교병원',school='한양대학교',aliases=['한양대학교병원','한양대병원'],
         region='서울',address='서울특별시 성동구 왕십리로 222-1',source='https://seoul.hyumc.com/'),
    dict(name='한양대학교암병원',school='한양대학교',aliases=['한양대학교암병원','한양대암병원'],
         region='서울',address='서울특별시 성동구 왕십리로 222-1',source='https://seoul.hyumc.com/tp/cancer/conts.do?tplMenuCd=002004000000000'),
    dict(name='건양대학교병원',school='건양대학교',aliases=['건양대학교병원','건양대병원'],
         region='대전',address='대전광역시 서구 관저동로 158',source='https://www.kyuh.ac.kr/ocs/'),
    dict(name='동국대학교일산병원',school='동국대학교',aliases=['동국대학교일산병원','동국대일산병원','동국대학교일산불교병원','동국대일산불교병원'],
         region='경기도',address='경기도 고양시 일산동구 동국로 27',source='https://www.dumc.or.kr/is/'),
    dict(name='동국대학교일산한방병원',school='동국대학교',aliases=['동국대학교일산한방병원','동국대일산한방병원'],
         region='경기도',address='경기도 고양시 일산동구 동국로 27',source='https://www.dumc.or.kr/isom/conts/104006000000000.do'),
    dict(name='가톨릭대학교인천성모병원',school='가톨릭대학교',aliases=['가톨릭대학교인천성모병원','가톨릭대인천성모병원','인천성모병원'],
         region='인천',address='인천광역시 부평구 동수로 56',source='https://mgrdc.cmcism.or.kr/theme/s007/index/location.php'),
    dict(name='가톨릭대학교은평성모병원',school='가톨릭대학교',aliases=['가톨릭대학교은평성모병원','가톨릭대은평성모병원','은평성모병원'],
         region='서울',address='서울특별시 은평구 통일로 1021',source='https://www.cmcep.or.kr/'),
    dict(name='가톨릭대학교성빈센트병원',school='가톨릭대학교',aliases=['가톨릭대학교성빈센트병원','가톨릭대성빈센트병원','성빈센트병원'],
         region='경기도',address='경기도 수원시 팔달구 중부대로 93',source='https://www.cmcvincent.or.kr/'),
    dict(name='단국대학교병원',school='단국대학교',aliases=['단국대학교병원','단국대병원'],
         region='충남',address='충청남도 천안시 동남구 망향로 201',source='https://www.dkuh.co.kr/mobile_2016/01/2025_dkuh_inpatient.pdf'),
    dict(name='순천향대학교서울병원',school='순천향대학교',aliases=['순천향대학교부속서울병원','순천향대학교서울병원','순천향대서울병원'],
         region='서울',address='서울특별시 용산구 대사관로 59',source='https://schmc.ac.kr/seoul/index.do'),
    dict(name='순천향대학교부천병원',school='순천향대학교',aliases=['순천향대학교부속부천병원','순천향대학교부천병원','순천향대부천병원'],
         region='경기도',address='경기도 부천시 원미구 조마루로 170',source='https://schmc.ac.kr/bucheon/index.do'),
    dict(name='순천향대학교구미병원',school='순천향대학교',aliases=['순천향대학교부속구미병원','순천향대학교구미병원','순천향대구미병원'],
         region='경북',address='경상북도 구미시 1공단로 179',source='https://schmc.ac.kr/gumi/index.do'),
    dict(name='순천향대학교천안병원',school='순천향대학교',aliases=['순천향대학교부속천안병원','순천향대학교천안병원','순천향대천안병원'],
         region='충남',address='충청남도 천안시 동남구 순천향6길 31',source='https://www.schmc.ac.kr/cheonan/contents.do?key=2886'),
    dict(name='인제대학교부산백병원',school='인제대학교',aliases=['인제대학교부산백병원','인제대부산백병원','부산백병원'],
         region='부산',address='부산광역시 부산진구 복지로 75',source='https://www.paik.ac.kr/busan/'),
    dict(name='한양대학교구리병원',school='한양대학교',aliases=['한양대학교구리병원','한양대구리병원','한양대구리'],
         region='경기도',address='경기도 구리시 경춘로 153',source='https://guri.hyumc.com/search/search.do'),
    dict(name='고려대학교구로병원',school='고려대학교',aliases=['고려대학교구로병원','고려대구로병원','고대구로병원'],
         region='서울',address='서울특별시 구로구 구로동로 148',source='https://guro.kumc.or.kr/kr/service-guide/hospital-information/directions.do'),
    dict(name='건국대학교병원',school='건국대학교',aliases=['건국대학교병원','건국대병원'],
         region='서울',address='서울특별시 광진구 능동로 120-1',source='https://www.kuh.ac.kr/english/guide/directions.do'),
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
    candidates=[]
    for record in FACILITIES:
        for alias in record['aliases']:
            for match in re.finditer(r'(?<![가-힣A-Za-z0-9])'+r'\s*'.join(map(re.escape,alias)),text):
                if re.match(r'\s*분원',text[match.end():]):continue
                candidates.append((match.start(),match.end(),record))
                # '순천향대 서울병원·부천병원'처럼 같은 대학의 병원을 대학명 없이 이어 쓴 경우입니다.
                position=match.end()
                while (tail:=re.match(r'\s*[·,]\s*([가-힣]{1,6}병원)',text[position:])):
                    sibling=next((r for r in FACILITIES if r['school']==record['school'] and r is not record
                                  and r['name'].endswith(tail.group(1))),None)
                    if sibling is None:break
                    candidates.append((position+tail.start(1),position+tail.end(1),sibling))
                    position+=tail.end()
    # 동일 구간은 가장 긴 기관명이 우선입니다. 같은 병원을 약칭/정식명으로 중복 등록하지 않습니다.
    spans=[]
    for start,end,record in sorted(candidates,key=lambda item:(-(item[1]-item[0]),item[0])):
        if any(start<old_end and old_start<end for old_start,old_end in spans):continue
        spans.append((start,end))
        if record not in matches:matches.append(record)
    for start,end in sorted(spans,reverse=True):text=text[:start]+' '*(end-start)+text[end:]
    return text,matches
