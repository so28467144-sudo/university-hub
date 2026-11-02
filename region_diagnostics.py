"""분류 결과의 근거와 실패 사유. 분류를 강제하거나 기사를 삭제하지 않습니다."""
import csv
import io
import json
import re
import unicodedata
from pathlib import Path
from collections import Counter
from university_regions import PATTERN,ALIAS_CANDIDATES,compact,select_alias_name,ADDRESS_RECORDS,REGISTRY,normalize_university_text

REASONS=('대학명 인식 실패','대학 주소록 미등록','대학명 중복 또는 모호함','캠퍼스 특정 불가',
         '대학 소재지와 기사 지역 불일치','기사에 여러 대학 등장','학력·출신 대학만 언급','기타')
GENERAL={'국내대학','지역대학','지방대학','전문대학','국립대학','사립대학','대학','대학교','우리대학',
         '일반대학','선도대학','지원대학','공유대학','국립대학교','세계대학','폐교대학','년제대학',
         '약학대학','의과대학','미술대학','정보대학','단과대학','기술혁신대학','혁신융합대학','행정대학'}

def diagnose_article(item):
    text=normalize_university_text(item['title']+'\n'+item.get('body',''))
    ambiguous=[];recognized=[];unknown=[]
    for match in PATTERN.finditer(text):
        name=select_alias_name(match,text)
        if name:recognized.append(name)
        elif len(ALIAS_CANDIDATES[compact(match.group())])>1:
            ambiguous.append(dict(text=match.group(),candidates=sorted(ALIAS_CANDIDATES[compact(match.group())])))
    for candidate in re.findall(r'(?<![가-힣])([가-힣]{2,}(?:대학교|대학|공전|교대))(?!원)',text):
        if candidate in GENERAL or re.search(r'농업|노인|시민|군민|여성|평생|박물관|도민|대학원|열린대학',candidate):continue
        if not any(select_alias_name(m,candidate) for m in PATTERN.finditer(candidate)):unknown.append(candidate)
    for candidate in re.findall(r'\b((?:[A-Z][A-Za-z-]+\s+){1,5}(?:University|College))\b',text):
        if not any(select_alias_name(m,candidate) for m in PATTERN.finditer(candidate)):unknown.append(candidate)
    schools=item.get('universities',[])
    extracted=sorted(set(recognized)|set(item.get('school_names',[]))|set(unknown)|{a['text'] for a in ambiguous})
    reasons=[]
    def add(reason):
        if reason not in reasons:reasons.append(reason)
    if ambiguous:add('대학명 중복 또는 모호함')
    background=item.get('background_universities',[])
    if background and not schools and not item.get('foreign_universities'):add('학력·출신 대학만 언급')
    if not item.get('school_names') and not (background and not schools):add('대학명 인식 실패')
    if unknown or any(not ADDRESS_RECORDS.get(u['name']) and u.get('method') not in ('national_network',) and u.get('affiliation_type')!='university_hospital' for u in schools):add('대학 주소록 미등록')
    if any(u.get('method') in ('national_network','campus_ambiguous','campus_unresolved') or u.get('campus_status')=='unresolved' for u in schools):add('캠퍼스 특정 불가')
    if len(schools)>1:add('기사에 여러 대학 등장')
    candidates={r for u in schools for r in u.get('candidate_regions',u.get('regions',[]))}
    outside=[p for p in item.get('mentioned_regions',[]) if candidates and p['region']!='해외' and p['region'] not in candidates]
    if outside:add('대학 소재지와 기사 지역 불일치')
    if not item.get('regions') and not reasons:add('기타')
    directory_matches=[dict(name=u['name'],matched=bool(ADDRESS_RECORDS.get(u['name'])) or u.get('affiliation_type')=='university_hospital',
                                candidate_regions=u.get('candidate_regions',u.get('regions',[])),region_resolution=u.get('region_resolution','legacy')) for u in schools]
    for name in sorted((set(recognized)|set(unknown))-{u['name'] for u in schools}):
        directory_matches.append(dict(name=name,matched=bool(ADDRESS_RECORDS.get(name)),candidate_regions=REGISTRY.get(name,[]),
                                      region_resolution='non_subject_mention' if name in REGISTRY else 'directory_missing'))
    return dict(id=item.get('id'),title=item['title'],url=item.get('original_url') or item.get('url',''),
        extracted_universities=extracted,
        directory_matches=directory_matches,
        campus_checks=[dict(name=u['name'],campuses=u.get('campus_names',[]),status=u.get('campus_status'),confirmed=u.get('campus_status')=='matched') for u in schools],
        failure_reasons=reasons if not item.get('regions') else [],review_reasons=reasons,
        classified=bool(item.get('regions')),result=item.get('regions',[]),ambiguous_names=ambiguous,
        additional_confirmation_names=sorted(set(unknown)|{u['name'] for u in schools if u.get('method') in ('national_network','campus_ambiguous','campus_unresolved') or not ADDRESS_RECORDS.get(u['name']) and u.get('affiliation_type')!='university_hospital'}|{name for a in ambiguous for name in a['candidates']}),
        background_universities=background,conflicting_region_evidence=outside)

def export_diagnostics(items,json_path,csv_path,only_unclassified=False):
    rows=[diagnose_article(item) for item in items]
    unresolved=[r for r in rows if not r['classified']]
    counts=Counter(reason for row in unresolved for reason in row['failure_reasons'])
    names=sorted({name for row in unresolved for name in row['additional_confirmation_names']})
    queue=[dict(name=name,article_count=sum(name in row['additional_confirmation_names'] for row in unresolved),
                articles=[dict(id=row['id'],title=row['title'],url=row['url']) for row in unresolved if name in row['additional_confirmation_names']]) for name in names]
    payload=dict(total=len(rows),classified=sum(r['classified'] for r in rows),unclassified=sum(not r['classified'] for r in rows),
                 unclassified_percent=round(len(unresolved)/len(rows)*100,2) if rows else 0,
                 failure_reason_counts={reason:counts[reason] for reason in REASONS},
                 additional_confirmation_names=queue,
                 reason_counts_overlap=True,
                 articles=unresolved if only_unclassified else rows)
    json_path=Path(json_path);csv_path=Path(csv_path)
    if json_path.resolve()==csv_path.resolve():raise ValueError('JSON과 CSV 출력 경로는 달라야 합니다.')
    Path(json_path).parent.mkdir(parents=True,exist_ok=True)
    Path(csv_path).parent.mkdir(parents=True,exist_ok=True)
    temp=Path(str(json_path)+'.tmp');temp.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(json_path)
    stream=io.StringIO(newline='');fields=['id','title','url','extracted_universities','directory_matches','campus_checks','failure_reasons','review_reasons','result','additional_confirmation_names']
    writer=csv.DictWriter(stream,fieldnames=fields,lineterminator='\n');writer.writeheader()
    for row in payload['articles']:
        cells={key:json.dumps(row[key],ensure_ascii=False) if isinstance(row[key],(list,dict)) else row[key] for key in fields}
        writer.writerow({key:"'"+value if isinstance(value,str) and value.startswith(('=','+','-','@')) else value for key,value in cells.items()})
    temp=Path(str(csv_path)+'.tmp');temp.write_text(stream.getvalue(),encoding='utf-8-sig');temp.replace(csv_path)
    return payload


def generate_report(input_path,output_dir,git_ref=None,git='git'):
    """저장된 분류만 진단하며 재분류하거나 입력 파일을 수정하지 않습니다."""
    import hashlib
    import subprocess
    input_path=Path(input_path).resolve();output_dir=Path(output_dir).resolve()
    outputs=[output_dir/name for name in ('diagnostics.json','diagnostics.csv','review_universities.json')]
    if input_path in outputs:raise ValueError('입력 파일과 리포트 출력 경로가 겹칩니다.')
    original=input_path.read_bytes() if input_path.exists() else None
    raw=subprocess.check_output([git,'show',git_ref+':news.json'],cwd=input_path.parent) if git_ref else original
    if raw is None:raise FileNotFoundError(input_path)
    data=json.loads(raw)
    if not isinstance(data.get('news'),list):raise ValueError('news 배열이 없는 입력입니다.')
    if any(not isinstance(row,dict) or not isinstance(row.get('title'),str) for row in data['news']):
        raise ValueError('기사 제목 형식이 올바르지 않습니다.')
    payload=export_diagnostics(data['news'],outputs[0],outputs[1],only_unclassified=True)
    payload['source']=dict(path=str(input_path),git_ref=git_ref,sha256=hashlib.sha256(raw).hexdigest(),
                           classification_mode='stored_results_without_reclassification')
    outputs[0].write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    outputs[2].write_text(json.dumps(payload['additional_confirmation_names'],ensure_ascii=False,indent=2),encoding='utf-8')
    assert (input_path.read_bytes() if input_path.exists() else None)==original,'진단 도중 입력 파일이 외부에서 변경되었습니다.'
    return payload


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='저장된 지역 분류 진단. 수집·재분류·뉴스 변경 없이 실행합니다.')
    parser.add_argument('--input',type=Path,default=Path(__file__).resolve().parent/'news.json')
    parser.add_argument('--output-dir',type=Path,default=Path(__file__).resolve().parent/'reports/diagnostics')
    parser.add_argument('--git-ref',help='명시한 Git 버전의 news.json을 읽습니다. 자동 대체하지 않습니다.')
    parser.add_argument('--git',default='git')
    args=parser.parse_args()
    try:
        result=generate_report(args.input,args.output_dir,args.git_ref,args.git)
    except (ValueError,OSError) as error:
        parser.exit(1,f'진단 실패: {error}\n입력은 변경하지 않았습니다. 병합 충돌 여부와 입력 JSON을 확인하세요.\n')
    print(json.dumps({key:result[key] for key in ('total','classified','unclassified','unclassified_percent','failure_reason_counts')},ensure_ascii=False))
    print(f'리포트 저장: {args.output_dir}')
