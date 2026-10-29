"""저장 기사에서 오분류 가능성이 높은 항목을 별도 검토용으로 추출합니다."""
import json
from pathlib import Path
from collections import Counter
from datetime import datetime,timedelta,timezone

ROOT=Path(__file__).resolve().parent

def review(rows):
    groups={
        'unresolved_campuses':[n for n in rows if any(u.get('campus_status')=='unresolved' for u in n.get('universities',[]))],
        'foreign_regions':[n for n in rows if '해외' in n.get('regions',[])],
        'unknown_university':[n for n in rows if not n.get('school_names')],
        'summary_added_regions':[n for n in rows if any(p['method']=='summary_region' and p['region'] not in {r for u in n.get('universities',[]) for r in u['regions']} for p in n.get('mentioned_regions',[]))],
        'background_only_universities':[n for n in rows if n.get('background_universities')],
    }
    return dict(raw_count=len(rows),counts={k:len(v) for k,v in groups.items()},
                review_groups={k:[{f:n.get(f) for f in ('id','title','body','school','regions','universities','mentioned_regions','url','source')} for n in v] for k,v in groups.items()})

if __name__=='__main__':
    import sys
    import argparse
    from university_regions import reclassify_article
    from article_dedup import deduplicate
    parser=argparse.ArgumentParser()
    parser.add_argument('--apply',action='store_true',help='재분류를 캐시에 적용합니다. 서버를 중지한 상태에서 실행하세요.')
    parser.add_argument('--continue-review',action='store_true',help='같은 점검 중 추가 수정 시 기존 변경 전 값을 보존합니다.')
    args=parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    data=json.loads((ROOT/'.rss-cache.json').read_text(encoding='utf-8'))
    previous={}
    if args.continue_review:
        previous={n['id']:n for n in json.loads((ROOT/'classification_changes.json').read_text(encoding='utf-8'))['changes']}
    rows=[];changes=[]
    for old in data['raw_news']:
        new=reclassify_article(old);rows.append(new)
        differences={key:dict(before=old.get(key),after=new.get(key)) for key in ('school','regions','category') if old.get(key)!=new.get(key)}
        if old['id'] in previous:
            for key,value in previous[old['id']]['changes'].items():
                if value['before']!=new.get(key):differences[key]=dict(before=value['before'],after=new.get(key))
                else:differences.pop(key,None)
        if differences:changes.append(dict(id=new['id'],title=new['title'],changes=differences))
        assert old.get('url')==new.get('url') and old.get('date')==new.get('date')
        assert set(new['regions'])==set(r for u in new['universities'] for r in u['regions'])|set(p['region'] for p in new['mentioned_regions'])
    assert len({n['id'] for n in rows})==len(rows)
    result=review(rows)
    result.update(checked_at=datetime.now(timezone(timedelta(hours=9))).isoformat(),
                  changed_count=len(changes),field_changes=dict(Counter(k for n in changes for k in n['changes'])),
                  changes=changes,applied=args.apply,classification_version=4)
    if args.apply:
        data['raw_news']=rows
        unique=deduplicate(rows)
        data['news']=unique[:5000]
        temp=ROOT/'.rss-cache.reclassification.tmp'
        temp.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
        temp.replace(ROOT/'.rss-cache.json')
        result.update(unique_count=len(unique),duplicates_removed=len(rows)-len(unique))
    (ROOT/'classification_review_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'classification_changes.json').write_text(json.dumps(dict(raw_count=len(rows),changed_count=len(changes),field_changes=result['field_changes'],changes=changes),ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# 기사 분류 재점검 결과','',f"점검 시각: {result['checked_at']} (한국 시간)",'',
           f"원본 {len(rows):,}건을 자동 재검사하고 의심 유형을 검토했습니다. 대학명·지역·기사 구분이 바뀐 기사는 {len(changes):,}건입니다.",'',
           '항목별 변경 수는 같은 기사를 중복 포함합니다: '+str(result['field_changes']),'',
           '수정한 원인: 정책명·기사 코너명·대학 연합 표현의 대학명 오인, 해외 동명 기관, 부속병원의 별도 소재지, 캠퍼스 일반 표현과 공동캠퍼스, 약칭 누락, 유학생 국적의 해외 지역 오인, 입시 키워드 부분 일치, 학력과 교육행사 혼동.','',
           '제목을 우선해 기사 구분을 재판정했습니다. 원문·게시일은 유지했습니다. 화면과 엑셀에는 재분류 후 중복 대표 기사가 표시됩니다.','',
           '## 확인한 공식 근거','',
           '- [타슈켄트 아주대학교 소개](https://abiz.ajou.ac.kr/kr/ajou/aut.do)',
           '- [인하공업전문대학의 인하공전 약칭 사용](https://cstem.inhatc.ac.kr/sites/kr/index.do)',
           '- [한신대학교 경기캠퍼스 안내](https://hs.ac.kr/)',
           '- [분당서울대학교병원 주소](https://www.snubh.org/index.do)',
           '- [화순전남대학교병원 주소](https://www.cnuhh.com/cnuhh/main.cs)','',
           '## 검토 한계','',
           'RSS 제목과 제공된 요약·공식 주소 자료를 기준으로 점검했습니다. 모든 원문을 사람이 읽은 전수 검수는 아닙니다. 주소 근거가 없는 신설 캠퍼스나 대학명이 없는 정책 기사는 임의로 채우지 않습니다.','',
           '전체 변경 전후는 classification_changes.json, 남은 검토 후보는 classification_review_report.json에서 확인할 수 있습니다.']
    (ROOT/'classification_review.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('RAW',len(rows),'CHANGED',len(changes),'FIELDS',result['field_changes'])
    print(result['counts'])
    for key,rows in result['review_groups'].items():
        print('\n'+key)
        for n in rows[:45]:print(n['id'],n['title'],'|',n['school'],'|',n['regions'])
