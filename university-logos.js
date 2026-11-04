// 기사 목록 왼쪽에 표시할 대학 공식 로고 목록입니다.
//
// 공식 출처와 외부 사용 조건(사용 허락 문서 또는 공개 라이선스)이 확인된 로고만 entries에 넣습니다.
// entries에 없는 대학, 대학명 미확인 기사, 여러 대학 기사, 로고 파일을 불러오지 못한 경우에는
// 중립적인 기본 아이콘을 표시합니다.
//
// entries 항목 형식
//   school       기사 데이터의 대학 정식명(school_names 값과 같아야 합니다)
//   aliases      같은 대학을 가리키는 다른 정식명(선택)
//   campus       캠퍼스 전용 로고일 때 캠퍼스명(선택). 기사에서 그 캠퍼스가 확인될 때만 씁니다.
//   file         저장소의 logos/ 폴더 안 파일 경로(외부 주소는 쓰지 않습니다)
//   source_url   로고를 받은 대학 공식 페이지
//   terms_url    외부 사용을 허락한 문서나 라이선스 주소
//   terms        허락 범위 요약
//   verified_at  확인한 날짜(YYYY-MM-DD)
//
// reviewed는 확인했지만 외부 사용 조건이 충족되지 않아 넣지 않은 대학의 기록입니다.
window.UNIVERSITY_LOGOS={
 entries:[],
 reviewed:[
  {school:'서울대학교',checked_at:'2026-11-04',source_url:'https://identity.snu.ac.kr/ui/1',
   status:'외부 사용 허가 필요',note:'정장은 상표 등록되어 있고 동문·외부인 사용은 산학협력단 지식재산관리부 허가가 필요합니다.'},
  {school:'고려대학교',checked_at:'2026-11-04',source_url:'https://www.korea.ac.kr/ko/373/subview.do',
   status:'외부 사용 허가 필요',note:'상업적 이용과 허가는 학교법인 상표권 담당 부서 문의 대상입니다.'},
  {school:'연세대학교',checked_at:'2026-11-04',source_url:'https://devcms.yonsei.ac.kr/designcenter/UI_mng/ui_mng.do',
   status:'외부 사용 허가 필요',note:'상표 등록되어 있고 파일은 교직원에게 교육·행정 목적으로만 제공됩니다.'},
  {school:'부산대학교',checked_at:'2026-11-04',source_url:'https://www.pusan.ac.kr/kor/CMS/Contents/Contents.do?mCode=MN154',
   status:'외부 사용 허가 필요',note:'상징 이미지는 교직원·학생의 교육·행정 목적에 한해 제공됩니다.'},
  {school:'전북대학교',checked_at:'2026-11-04',source_url:'https://www.jbnu.ac.kr/web/intro/university/sub05.do',
   status:'사용 조건 미확인',note:'제작용 데이터 다운로드 안내는 있으나 외부 사용 허락 조건이 명시되어 있지 않습니다.'},
  {school:'제주대학교',checked_at:'2026-11-04',source_url:'https://www.jejunu.ac.kr/promotion/designcenter/ui.htm',
   status:'사용 조건 미확인',note:'UI 다운로드 메뉴는 있으나 외부 사용 허락 조건이 명시되어 있지 않습니다.'}
 ]
};
