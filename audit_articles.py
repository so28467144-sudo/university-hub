"""저장 기사 중복 및 지역 분류를 다시 검사하고 검토 보고서를 만듭니다."""
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from article_dedup import deduplicate,normalize,same_story
from university_regions import reclassify_article,explicit_title_regions

ROOT=Path(__file__).resolve().parent


def audit(raw,visible):
    classified=[reclassify_article(n) for n in raw]
    unique=deduplicate(classified)
    by_title=defaultdict(list)
    for n in visible:by_title[re.sub(r'\W','',normalize(n['title']))].append(n)
    remaining=[]
    for group in by_title.values():
        for i,first in enumerate(group):
            for second in group[i+1:]:
                if same_story(first,second):remaining.append(dict(first_id=first['id'],second_id=second['id'],title=first['title']))
    unclassified=[n for n in classified if not n['regions']]
    identified=[n for n in unclassified if any(u.get('method')!='national_network' for u in n.get('universities',[]))]
    explicit=[n for n in unclassified if explicit_title_regions(n['title'])]
    examples=lambda rows:[dict(id=n['id'],title=n['title'],universities=n.get('universities',[]),url=n.get('url')) for n in rows[:100]]
    return dict(checked_at=datetime.now(timezone.utc).isoformat(),raw_count=len(raw),visible_count=len(visible),
                unique_count=len(unique),duplicates_removed=len(raw)-len(unique),
                duplicate_groups=sum(n['duplicate_count']>1 for n in unique),
                remaining_exact_duplicate_pairs=remaining,
                unclassified_count=len(unclassified),identified_university_but_no_region_count=len(identified),
                explicit_region_but_unclassified_count=len(explicit),
                identified_university_review=examples(identified),explicit_region_review=examples(explicit),
                unclassified_review=examples(unclassified))


def main():
    data=json.loads((ROOT/'.rss-cache.json').read_text(encoding='utf-8'))
    report=audit(data.get('raw_news',data['news']),data['news'])
    (ROOT/'article_audit_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k.endswith('_count') or k in ('duplicate_groups','duplicates_removed')},ensure_ascii=False))
    print('Remaining exact duplicate pairs:',len(report['remaining_exact_duplicate_pairs']))


if __name__=='__main__':main()
