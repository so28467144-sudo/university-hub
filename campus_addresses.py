"""캠퍼스 명칭과 공공 주소록 레코드를 연결하는 선택 규칙."""
# (표시 이름, 기사에 쓰이는 표기, 주소에 포함되는 고유 도로명)
CAMPUS_SELECTORS = {
    '성균관대학교': [('자연과학캠퍼스',['자연과학캠퍼스','수원캠퍼스'],'서부로 2066'),('인문사회과학캠퍼스',['인문사회과학캠퍼스','서울캠퍼스'],'성균관로 25-2')],
    '부산가톨릭대학교': [('하하캠퍼스',['하하캠퍼스'],'기찰로102번길 56-7')],
    '한국조지메이슨대학교': [('한국캠퍼스',['한국캠퍼스'],'송도문화로 119')],
    '한신대학교': [('경기캠퍼스',['경기캠퍼스','오산캠퍼스'],'한신대길 137')],
    '상명대학교': [('천안캠퍼스', ['천안캠퍼스', '(천안)'], '상명대길 31'), ('서울캠퍼스', ['서울캠퍼스', '(서울)'], '홍지문2길 20')],
    '인천대학교': [('송도캠퍼스', ['송도캠퍼스'], '아카데미로 119')],
    '인제대학교': [('김해캠퍼스', ['김해캠퍼스'], '인제로 197'), ('부산캠퍼스', ['부산캠퍼스'], '복지로 75')],
    '한양대학교': [('ERICA캠퍼스', ['ERICA', '에리카'], '한양대학로 55'), ('서울캠퍼스', ['서울캠퍼스', '(서울)'], '왕십리로 222')],
    '연세대학교': [('미래캠퍼스', ['미래캠퍼스', '(미래)', '원주캠퍼스'], '연세대길 1'), ('신촌캠퍼스', ['신촌캠퍼스', '서울캠퍼스'], '연세로 50'), ('국제캠퍼스', ['국제캠퍼스', '송도캠퍼스'], '송도과학로 85')],
    '단국대학교': [('죽전캠퍼스', ['죽전캠퍼스', '(죽전)'], '죽전로 152'), ('천안캠퍼스', ['천안캠퍼스', '(천안)'], '단대로 119')],
    '명지대학교': [('자연캠퍼스', ['자연캠퍼스', '용인캠퍼스'], '명지로 116'), ('인문캠퍼스', ['인문캠퍼스', '서울캠퍼스'], '거북골로 34')],
    '경동대학교': [('메트로폴캠퍼스', ['메트로폴캠퍼스', '양주캠퍼스'], '경동대학로 27'), ('메디컬캠퍼스', ['메디컬캠퍼스', '원주캠퍼스'], '견훤로 815'), ('글로벌캠퍼스', ['글로벌캠퍼스', '고성캠퍼스'], '봉포4길 46')],
    '선문대학교': [('아산캠퍼스', ['아산캠퍼스', '(아산)'], '선문로221번길 70'), ('천안캠퍼스', ['천안캠퍼스', '(천안)'], '천안대로 277')],
}

# 대학명에 바로 붙은 고유 표현만 기존 주소 레코드와 연결합니다. 일반 지명 사전이 아닙니다.
CAMPUS_IDENTITY_CUES = [
    dict(school='동국대학교',label='WISE캠퍼스',aliases=['WISE','와이즈'],road='동대로 123',
         source='https://wise.dongguk.ac.kr/page/110'),
    dict(school='연세대학교',label='미래캠퍼스',aliases=['미래'],road='연세대길 1',
         after_pattern=r'\s*(?:캠퍼스|출결|논술|수시|정시|입학)',source='https://www.yonsei.ac.kr/wj/1483/subview.do'),
    dict(school='인제대학교',label='김해캠퍼스',aliases=['김해'],position='before',road='인제로 197',
         source='https://www.data.go.kr/data/15107736/standard.do'),
    dict(school='안양대학교',label='안양캠퍼스',aliases=['유아교육과'],road='삼덕로37번길 22',
         source='https://www.anyang.ac.kr/main/introduction/anyang-campus001.do'),
    dict(school='고려대학교',label='세종캠퍼스',aliases=['세종앵커사업단'],road='세종로 2511',
         source='https://csg.korea.ac.kr/bbs/news/241/273375/artclView.do'),
]

# 공공 주소록에 빠진 캠퍼스는 대학 공식 안내로 보완하며 출처를 함께 저장합니다.
SUPPLEMENTS = [
    dict(name='성균관대학교',original_name='성균관대학교 자연과학캠퍼스',campus='자연과학캠퍼스',region='경기도',address='경기도 수원시 장안구 서부로 2066',source='https://www.skku.edu/_res/skku/etc/yr2022.pdf'),
    dict(name='부산가톨릭대학교',original_name='부산가톨릭대학교 하하캠퍼스',campus='하하캠퍼스',region='부산',address='부산광역시 금정구 기찰로102번길 56-7',source='https://www.busan.go.kr/hahacampus/about06'),
    dict(name='한국조지메이슨대학교', original_name='한국조지메이슨대학교 한국캠퍼스', campus='한국캠퍼스', region='인천', address='인천광역시 연수구 송도문화로 119', source='https://www.yeonsu.go.kr/main/part/education/facility.asp?bcode=14'),
    dict(name='한국외국어대학교', original_name='한국외국어대학교 글로벌캠퍼스', campus='글로벌캠퍼스', region='경기도', address='경기도 용인시 처인구 모현읍 외대로 81', source='https://onestop.hufs.ac.kr/onestop/index.do'),
    dict(name='연세대학교', original_name='연세대학교 국제캠퍼스', campus='국제캠퍼스', region='인천', address='인천광역시 연수구 송도과학로 85', source='https://www.yonsei.kr/sc/316/subview.do'),
    dict(name='선문대학교', original_name='선문대학교 천안캠퍼스', campus='천안캠퍼스', region='충남', address='충청남도 천안시 동남구 천안대로 277', source='https://www.studyinkorea.go.kr/file/srcFileDown.do?fileStorePath=fileStorePath&filename=81_530640_202108250156088300.pdf&orgfilename=2021+Admission+Guide+Korean+Language+Institute+Sun+Moon+University.pdf'),
]
