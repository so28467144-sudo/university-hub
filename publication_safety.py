"""공개 뉴스 교체 전 보존 검사. 분류 규칙과 별개인 자동 갱신 경계입니다."""
import json
from rss_summaries import assess_summary, USEFUL_KINDS

CORE_FIELDS = ('id', 'title', 'url', 'original_url', 'date', 'body')


class PublicationBlocked(RuntimeError):
    pass


def verified_unknown_fill(previous, proposed):
    """Only fill an empty public region from independently reproducible evidence."""
    if previous.get('regions') != [] or not proposed.get('regions'):return False
    from university_regions import reclassify_article
    decision=reclassify_article(previous)
    schools=decision.get('universities',[])
    if set(decision['regions'])!=set(proposed['regions']) or decision.get('conflicting_region_evidence'):return False
    if not schools:
        # 대학이 없는 기사는 제목에 명시된 국내 지역 근거만 인정합니다.
        titled={p['region'] for p in decision.get('mentioned_regions',[]) if p.get('method')=='title_region'}
        return not decision.get('foreign_universities') and '해외' not in decision['regions'] and set(decision['regions'])<=titled
    return all(
        u.get('addresses') and u.get('source') and u.get('regions') and u.get('region_resolution') in
        ('verified_campus','unique_verified_location','article_address_intersection','campus_place_match','main_campus_default') for u in schools) and set(decision['regions'])=={r for u in schools for r in u['regions']}


def verified_campus_correction(previous, proposed):
    """기존 지역이 대학 후보 지역에서만 왔고, 공식 주소의 병원·학과 근거가 다른 답을 줄 때만 교정합니다."""
    old=set(previous.get('regions') or [])
    if not old or not proposed.get('regions'):return False
    from university_regions import reclassify_article, REGISTRY, ADDRESS_RECORDS
    decision=reclassify_article(previous)
    schools=decision.get('universities',[])
    new=set(decision['regions'])
    if new!=set(proposed['regions']) or new==old or decision.get('conflicting_region_evidence') or not schools:return False
    if ('해외' in old)!=('해외' in new):return False
    # 기사에 직접 쓰인 지역은 대학 후보가 아니라 기사 근거이므로 바꾸지 않습니다.
    if any(p['region'] in old-new for p in decision.get('mentioned_regions',[])):return False
    candidates={r for u in schools for r in REGISTRY.get(u['name'],[])}|{r['region'] for u in schools for r in ADDRESS_RECORDS.get(u['name'],[])}
    if not (old-{'해외'})<=candidates:return False
    return all(u.get('region_resolution')=='verified_campus' and u.get('addresses') and u.get('source') and u.get('regions')
               and (u.get('affiliation_type')=='university_hospital' or u.get('campus_cue_evidence')
                    or (u.get('campus_status')=='matched' and u.get('campus_names'))) for u in schools) and \
        new-{'해외'}=={r for u in schools for r in u['regions']}


def merge_raw_record(previous, incoming):
    if not previous: return dict(incoming)
    if previous['id'] != incoming['id']: raise ValueError('Different raw article IDs')
    result = dict(previous)
    pending = dict(previous.get('pending_update', {}))
    for key in CORE_FIELDS:
        if previous.get(key) != incoming.get(key):
            if key == 'body' and 'body' in pending:
                old_quality = assess_summary(pending['body'], previous.get('title', ''))[1]
                if old_quality > assess_summary(incoming.get('body', ''), incoming.get('title', ''))[1]: continue
            pending[key] = incoming.get(key)
    if pending: result['pending_update'] = pending
    aliases = set(previous.get('duplicate_ids', [previous['id']])) | set(incoming.get('duplicate_ids', [])) | {previous['id']}
    result.update(duplicate_ids=sorted(aliases), duplicate_count=len(aliases))
    if incoming.get('last_seen'): result['last_seen'] = incoming['last_seen']
    if not result.get('first_seen') and incoming.get('first_seen'): result['first_seen'] = incoming['first_seen']
    return result


def merge_raw_sources(*sources):
    result = {}
    for rows in sources:
        for row in rows:
            result[row['id']] = merge_raw_record(result.get(row['id']), row)
    return list(result.values())


def region_review(previous, proposed):
    old, new = previous.get('regions', []), proposed.get('regions', [])
    if set(old) == set(new): return None
    schools = proposed.get('universities', [])
    verified = bool(new) and bool(schools) and all(
        u.get('regions') and u.get('addresses') and u.get('source') and
        u.get('region_resolution') in ('verified_campus', 'unique_verified_location', 'article_address_intersection')
        for u in schools) and not proposed.get('conflicting_region_evidence')
    return dict(id=previous['id'], title=previous['title'], url=previous.get('original_url') or previous.get('url'),
                previous_regions=old, proposed_regions=new, published_regions=old,
                decision='verified_correction_candidate' if verified else 'insufficient_evidence_keep_existing',
                reason='새 소재지 근거는 확인됐지만 기존 공개 결과의 오류를 확정하지 않아 수동 검토' if verified else '캠퍼스 미특정 또는 변경 근거 부족으로 기존 공개 결과 유지',
                previous_classification_version=previous.get('classification_version'),
                proposed_classification_version=proposed.get('classification_version'),
                automatic_change_applied=False, previous_evidence=previous.get('universities', []),
                proposed_evidence=schools, mentioned_regions=proposed.get('mentioned_regions', []))


def validate_rows(rows, label):
    errors = []; seen = set()
    if not isinstance(rows, list): return [dict(reason=label+'_not_list', ids=[])]
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id']:
            errors.append(dict(reason=label+'_invalid_id', ids=[])); continue
        if row['id'] in seen: errors.append(dict(reason=label+'_duplicate_id', ids=[row['id']]))
        seen.add(row['id'])
        if not isinstance(row.get('title'), str) or not isinstance(row.get('url'), str):
            errors.append(dict(reason=label+'_invalid_record', ids=[row['id']]))
        if any(key in row and not isinstance(row[key], str) for key in ('body', 'date')):
            errors.append(dict(reason=label+'_invalid_text_field', ids=[row['id']]))
        for key in ('regions', 'duplicate_ids'):
            if key in row and (not isinstance(row[key], list) or not all(isinstance(v, str) for v in row[key])):
                errors.append(dict(reason=label+'_invalid_'+key, ids=[row['id']]))
        try: json.dumps(row, allow_nan=False)
        except (TypeError, ValueError): errors.append(dict(reason=label+'_json_integrity', ids=[row['id']]))
    return errors


def publication_errors(previous_news, previous_raw, news, raw, new_ids=()):
    errors = validate_rows(news, 'public') + validate_rows(raw, 'raw')
    if errors: return errors
    old = {r['id']: r for r in previous_news}; new = {r['id']: r for r in news}
    old_raw = {r['id']: r for r in previous_raw}; new_raw = {r['id']: r for r in raw}
    def add(reason, ids):
        if ids: errors.append(dict(reason=reason, ids=sorted(ids)))
    add('raw_records_lost', old_raw.keys()-new_raw.keys())
    add('public_record_not_in_raw', new.keys()-new_raw.keys())
    missing = old.keys()-new.keys()
    if not new_ids: add('public_ids_lost_without_new_articles', missing)
    if len(news) < min(len(previous_news), 5000):
        errors.append(dict(reason='public_count_decreased', ids=sorted(missing)))
    if len(missing) > len(new.keys()-old.keys()): add('unexpected_public_eviction', missing)
    if len(news) > 5000: errors.append(dict(reason='public_limit_exceeded', ids=[]))
    for label, before, after in [('raw', old_raw, new_raw), ('public', old, new)]:
        for article_id in before.keys() & after.keys():
            a, b = before[article_id], after[article_id]
            if any(a.get(k) != b.get(k) for k in CORE_FIELDS): add(label+'_identity_content_changed', [article_id])
            if not set(a.get('duplicate_ids', [])).issubset(set(b.get('duplicate_ids', []))):
                add(label+'_duplicate_links_lost', [article_id])
            if assess_summary(a.get('body', ''), a.get('title', ''))[0] in USEFUL_KINDS and a.get('body') != b.get('body'):
                add(label+'_useful_summary_lost', [article_id])
            if label == 'public' and 'regions' in a and set(a.get('regions', [])) != set(b.get('regions', [])) and not verified_unknown_fill(a,b) and not verified_campus_correction(a,b):
                add('unapproved_existing_region_change', [article_id])
    return errors
