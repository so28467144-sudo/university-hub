"""NTIS 국가R&D통합공고 RSS 수집: rnd-announcements.json에 공고를 링크 기준으로 쌓아 보관합니다.

NTIS는 별도 API 없이 RSS 구독을 안내합니다(KISTEP NTIS팀 안내 자료, 2022.01).
주소: https://www.ntis.go.kr/rndgate/unRndRss.xml?prt=100 (최근 신규 공고, 최대 100건)

실행: python rnd_collector.py
과거 공고 채우기: python rnd_collector.py --backfill 2026-01-01 [--until 2026-11-17]
  RSS는 최근 100건만 주고 페이징(Fi)으로 그 이후를 받을 수 없어, 공고일(dt=YYYYMMDD)별로 하루씩 조회합니다.
수집이나 해석에 실패하면 기존 파일을 그대로 둡니다.
"""
import argparse
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / 'rnd-announcements.json'
FEED_URL = 'https://www.ntis.go.kr/rndgate/unRndRss.xml?prt=100'
DAY_URL = 'https://www.ntis.go.kr/rndgate/unRndRss.xml?prt=100&dt={day}'
LIST_URL = 'https://www.ntis.go.kr/rndgate/eg/un/ra/mng.do'
MAX_ITEMS = 5000
# 이 공고일(YYYY-MM-DD) 이후 공고와, 그 이전 공고 중 아직 마감되지 않은 것만 보관합니다. 기준을 없애려면 ''로 바꾸세요.
MIN_POSTED_DATE = '2026-10-01'
KST = timezone(timedelta(hours=9))

DEFAULT_CATEGORIES = {
    'status': ['접수예정', '접수중', '마감'],
    'ministry': [],
    'scale': ['1억미만', '1억이상 ~ 3억미만', '3억이상 ~ 5억미만', '5억이상'],
    'deadline': ['마감3일전', '마감1주전', '마감3주전', '마감1달전', '마감1달이상'],
}


def korean_today(now=None):
    return (now or datetime.now(timezone.utc)).astimezone(KST).date().isoformat()


def iso_date(value):
    """'2026.11.13', '2026-11-13', '20261113' 등을 'YYYY-MM-DD'로 바꿉니다. 해석할 수 없으면 ''."""
    match = re.search(r'(\d{4})\D?(\d{1,2})\D?(\d{1,2})', str(value or ''))
    if not match:
        return ''
    try:
        return datetime(*map(int, match.groups())).date().isoformat()
    except ValueError:
        return ''


def budget_won(value):
    digits = re.sub(r'[^\d]', '', str(value or ''))
    return int(digits) if digits else None


def announcement_status(open_date, close_date, today):
    """접수 시작일·마감일로 공고현황을 계산합니다. 날짜가 없으면 ''."""
    if close_date and close_date < today:
        return '마감'
    if open_date and open_date > today:
        return '접수예정'
    if open_date or close_date:
        return '접수중'
    return ''


def announcement_id(link):
    uid = parse_qs(urlsplit(link).query).get('roRndUid', [''])[0]
    return 'ntis-' + uid if uid.isdigit() else 'ntis-' + link


def parse_feed(raw):
    """NTIS RSS XML을 공고 목록으로 바꿉니다. 형식이 맞지 않으면 ValueError."""
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('DTD is not supported')
    root = ET.fromstring(raw)
    if root.tag != 'rss' or root.find('channel') is None:
        raise ValueError('Not an RSS feed')
    items = []
    for node in root.find('channel').findall('item'):
        text = lambda tag: ' '.join((node.findtext(tag) or '').split())
        title, link = text('title'), text('link')
        if not title or not link.startswith('https://www.ntis.go.kr/'):
            continue
        items.append(dict(
            id=announcement_id(link),
            title=title,
            url=link,
            ministry=text('author'),
            agency=text('category'),
            posted_date=iso_date(text('pubDate')),
            open_date=iso_date(text('appbegin')),
            close_date=iso_date(text('appdue')),
            budget_won=budget_won(text('budget')),
        ))
    return items


def merge(existing, incoming, today, min_posted=MIN_POSTED_DATE):
    """같은 공고(링크)는 한 번만 저장하고 최신 내용으로 갱신합니다. 공고일 최신순, 최대 MAX_ITEMS건.
    공고일이 min_posted보다 이른 공고는 아직 마감되지 않은 것(마감일이 오늘 이후)만 남깁니다.
    이전 공고는 마감되면 다음 수집 때 빠집니다. 공고일을 모르는 공고는 남깁니다."""
    def keep(item):
        if not min_posted or not item.get('posted_date') or item['posted_date'] >= min_posted:
            return True
        return bool(item.get('close_date')) and item['close_date'] >= today

    by_id = {}
    for item in existing:
        if isinstance(item, dict) and item.get('id') and keep(item):
            by_id[item['id']] = dict(item)
    added = 0
    for item in incoming:
        if not keep(item):
            continue
        if item['id'] not in by_id:
            added += 1
            by_id[item['id']] = dict(item, first_seen=today)
        else:
            by_id[item['id']].update(item)
    for item in by_id.values():
        item['status'] = announcement_status(item.get('open_date', ''), item.get('close_date', ''), today)
    rows = sorted(by_id.values(), key=lambda row: (row.get('posted_date') or '', row['id']), reverse=True)
    return rows[:MAX_ITEMS], added


def load(path):
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def build(previous, incoming, now=None):
    today = korean_today(now)
    items, added = merge(previous.get('items') or [], incoming, today)
    categories = dict(DEFAULT_CATEGORIES)
    known = [name for name in (previous.get('categories') or {}).get('ministry', []) if isinstance(name, str)]
    seen = {item['ministry'] for item in items if item.get('ministry')}
    categories['ministry'] = sorted(set(known) | seen)
    data = dict(
        source=dict(name='NTIS 국가R&D통합공고', url=LIST_URL, feed=FEED_URL),
        status='ok',
        updated_at=(now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(timespec='seconds'),
        categories=categories,
        items=items,
    )
    return data, added


def fetch(url=FEED_URL, timeout=20):
    request = Request(url, headers={'User-Agent': 'CampusOnRSS/1.0 (NTIS R&D RSS reader)'})
    with urlopen(request, timeout=timeout) as response:
        return response.read(5_000_000)


def update(path=DATA_PATH, raw=None, now=None):
    """수집 후 저장합니다. 성공하면 (전체 건수, 새 공고 수)를 돌려주고, 실패하면 예외를 냅니다(기존 파일 유지)."""
    incoming = parse_feed(raw if raw is not None else fetch())
    if not incoming:
        raise ValueError('NTIS RSS에 공고가 없습니다')
    data, added = build(load(path), incoming, now)
    save(path, data)
    return len(data['items']), added


def save(path, data):
    blob = json.dumps(data, ensure_ascii=False, indent=1, allow_nan=False) + '\n'
    temp = path.with_suffix('.tmp')
    temp.write_text(blob, encoding='utf-8')
    temp.replace(path)


def backfill(start, until, path=DATA_PATH, fetch_day=None, delay=0.5, now=None, log=print):
    """start~until 공고일을 하루씩 조회해 쌓습니다. 하루 조회가 실패하면 건너뛰고 실패한 날짜를 돌려줍니다.
    공고가 없는 날(주말 등)은 빈 RSS가 옵니다. 30일마다 중간 저장해 중단되어도 받은 만큼 남깁니다."""
    fetch_day = fetch_day or (lambda day: fetch(DAY_URL.format(day=day.strftime('%Y%m%d'))))
    data, failed, total_added, batch = load(path), [], 0, []

    def flush():
        nonlocal data, total_added, batch
        if batch:
            data, added = build(data, batch, now)
            save(path, data)
            total_added += added
            batch = []

    day = start
    while day <= until:
        try:
            batch.extend(parse_feed(fetch_day(day)))
        except Exception as error:
            failed.append(day.isoformat())
            log(f'{day} 조회 실패: {error}')
        if (day - start).days % 30 == 29:
            flush()
            log(f'{day} 까지 조회: 누적 {len(data.get("items", []))}건')
        day += timedelta(days=1)
        if delay and day <= until:
            time.sleep(delay)
    flush()
    return len(data.get('items', [])), total_added, failed


def main(argv=None):
    parser = argparse.ArgumentParser(description='NTIS 국가R&D통합공고 RSS 수집')
    parser.add_argument('--backfill', metavar='YYYY-MM-DD', help='이 공고일부터 하루씩 과거 공고를 채웁니다')
    parser.add_argument('--until', metavar='YYYY-MM-DD', help='채우기 마지막 날짜(기본: 오늘, 한국 시간)')
    args = parser.parse_args(argv)
    if args.backfill:
        start = date.fromisoformat(args.backfill)
        until = date.fromisoformat(args.until or korean_today())
        total, added, failed = backfill(start, until)
        print(f'rnd-announcements.json 채우기 완료: 전체 {total}건, 새 공고 {added}건, 실패한 날짜 {len(failed)}개')
        if failed:
            print('다시 시도할 날짜: ' + ', '.join(failed))
        return
    try:
        total, added = update()
    except Exception as error:  # 뉴스 갱신을 막지 않도록 실패만 알립니다.
        print(f'NTIS R&D 공고 수집 실패(기존 파일 유지): {error}', file=sys.stderr)
        sys.exit(1)
    print(f'rnd-announcements.json 갱신 완료: 전체 {total}건, 새 공고 {added}건')


if __name__ == '__main__':
    main()
