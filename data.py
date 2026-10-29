"""화면 개발용 예시 데이터. 외부 API를 호출하지 않습니다."""
from datetime import date, timedelta

REGIONS = ['전체 지역', '서울', '부산', '대구', '인천', '광주', '대전', '울산', '세종', '경기도', '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주', '해외', '지역 미분류']
CATEGORIES = ['전체', '입시·모집', '연구·성과', '행사·특강', '장학·지원', '캠퍼스']
SCHOOLS = [
    ('서울대학교', '서울', '서울', 'https://www.snu.ac.kr/', 'S'),
    ('강원대학교', '강원', '춘천', 'https://www.kangwon.ac.kr/', 'K'),
    ('충북대학교', '충북', '청주', 'https://www.chungbuk.ac.kr/', 'C'),
    ('충남대학교', '대전', '대전', 'https://www.cnu.ac.kr/', 'C'),
    ('전북대학교', '전북', '전주', 'https://www.jbnu.ac.kr/', 'J'),
    ('전남대학교', '광주', '광주', 'https://www.jnu.ac.kr/', 'J'),
    ('경북대학교', '대구', '대구', 'https://www.knu.ac.kr/', 'K'),
    ('부산대학교', '부산', '부산', 'https://www.pusan.ac.kr/', 'P'),
    ('제주대학교', '제주', '제주', 'https://www.jejunu.ac.kr/', 'J'),
]
TOPICS = [
    ('행사·특강', '가을 캠퍼스에서 만나는 인문학 공개 강연', '학생과 지역 주민이 함께 참여하는 공개 강연 소식을 살펴보세요.'),
    ('연구·성과', '새로운 가능성을 여는 융합 연구 프로젝트 소개', '다양한 학문이 만나 만들어 가는 캠퍼스 연구 이야기를 소개합니다.'),
    ('장학·지원', '학생의 도전을 응원하는 장학 지원 프로그램', '배움과 성장을 돕는 학생 지원 프로그램 안내 예시입니다.'),
    ('입시·모집', '신입생 모집과 입학 설명회 안내', '모집 일정과 지원 정보를 확인하는 소식 화면의 예시입니다.'),
    ('캠퍼스', '학생과 지역이 함께 만드는 캠퍼스 이야기', '대학의 일상과 지역사회 교류 활동을 만나보세요.'),
]


def get_demo_news():
    """고정된 예시 게시일로 반환하여 실제 최신 공지로 오인하지 않게 합니다."""
    result = []
    for i in range(27):
        school, region, city, url, mark = SCHOOLS[i % len(SCHOOLS)]
        category, title, body = TOPICS[i % len(TOPICS)]
        result.append(dict(
            id=str(i + 1), school=school, region=region, city=city,
            url=url, mark=mark, category=category, title=title, body=body,
            date=(date(2026, 10, 26) - timedelta(days=i // 2)).isoformat(),
        ))
    return result
