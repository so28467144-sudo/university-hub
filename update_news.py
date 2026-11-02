"""GitHub Actions의 RSS 갱신. 5,000건 정책과 공개 JSON 구조를 유지합니다."""
import json
from pathlib import Path
from rss_collector import Collector
from region_diagnostics import export_diagnostics
from publication_safety import merge_raw_sources, publication_errors, validate_rows, PublicationBlocked
from news_storage import load_state, prepare_pair, write_pair


def block_publication(root, reason, violations):
    report = dict(blocked=True, reason=reason, violations=violations)
    path = root/'publication_safety_report.json'
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    raise PublicationBlocked(reason)

def update_news(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parent
    news_path=root/'news.json';cache_path=root/'.rss-cache.json'
    previous={}
    original_bytes = news_path.read_bytes() if news_path.exists() else None
    if news_path.exists():
        try:
            previous=json.loads(original_bytes)
            if not isinstance(previous, dict) or not isinstance(previous.get('news'), list): raise ValueError('Invalid news array')
            json.dumps(previous, allow_nan=False)
            previous=load_state(root,previous)
            cached=json.loads(cache_path.read_bytes()) if cache_path.exists() else {}
            raw_sources=[previous.get('raw_news', []), cached.get('raw_news', cached.get('news', [])), previous['news']]
            violations=validate_rows(previous['news'], 'previous_public')
            for rows in raw_sources: violations.extend(validate_rows(rows, 'previous_raw'))
            if violations: block_publication(root, '입력 데이터 무결성 오류', violations)
            raw=merge_raw_sources(*raw_sources)
            previous_raw=raw
            seed_path=cache_path.with_suffix('.seed.tmp')
            seed_path.write_text(json.dumps(dict(news=previous['news'],raw_news=raw,
                lastSuccess=previous.get('status',{}).get('lastSuccess'),search_cursor=previous.get('search_cursor',0)),ensure_ascii=False,allow_nan=False),encoding='utf-8')
            seed_path.replace(cache_path)
        except PublicationBlocked: raise
        except (OSError, ValueError, TypeError, KeyError) as error:
            block_publication(root, '기존 JSON 무결성 오류: '+str(error), [dict(reason='input_json_integrity',ids=[])])
    else:
        previous_raw=[]
    collector=Collector();collector.refresh()
    news,status=collector.snapshot()
    if status['state']=='error':
        block_publication(root, '수집 또는 보존 검사 실패. 기존 news.json 유지', status.get('safety_violations', [dict(reason='collection_error', ids=[])]))
    if not news: block_publication(root, '빈 공개 결과 차단', [dict(reason='empty_public_news',ids=[])])
    raw=getattr(collector, 'raw_news', previous_raw)
    reviews=getattr(collector, 'region_change_reviews', [])
    violations=publication_errors(previous.get('news', []),previous_raw,news,raw,getattr(collector,'new_article_ids',set()))
    if violations: block_publication(root, '공개 교체 전 데이터 보존 검사 실패', violations)
    output=dict(previous,news=news,raw_news=raw,raw_news_schema_version=1,region_change_reviews=reviews,
                status=status,search_cursor=collector.search_cursor)
    output.pop('preservation',None)
    try:
        public_blob,state_blob=prepare_pair(output)
    except (TypeError,ValueError) as error:
        block_publication(root,'출력 JSON 무결성 오류: '+str(error),[dict(reason='output_json_integrity',ids=[])])
    if (news_path.read_bytes() if news_path.exists() else None)!=original_bytes:
        block_publication(root,'작업 도중 공개 파일 변경 감지',[dict(reason='concurrent_public_change',ids=[])])
    diagnostics=export_diagnostics(news,root/'classification_diagnostics.json',root/'classification_diagnostics.csv')
    diagnostics['region_change_reviews']=reviews
    (root/'classification_diagnostics.json').write_text(json.dumps(diagnostics,ensure_ascii=False,indent=2),encoding='utf-8')
    (root/'publication_safety_report.json').write_text(json.dumps(dict(blocked=False,public_count=len(news),raw_count=len(raw),region_change_review_count=len(reviews)),ensure_ascii=False,indent=2),encoding='utf-8')
    try:
        write_pair(root,public_blob,state_blob)
    except (OSError,RuntimeError) as error:
        block_publication(root,'데이터 쌍 저장 실패: '+str(error),[dict(reason='paired_storage_failure',ids=[row['id'] for row in news])])
    print(f'news.json 갱신 완료: {len(news)}건 (진단 JSON·CSV 생성)')
    return output

if __name__=='__main__':update_news()
