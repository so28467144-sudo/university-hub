"""API 키 없는 RSS/Atom 수집기. Python 표준 라이브러리만 사용합니다."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / '.rss-cache.json'
INTERVAL = 1800
MAX_ARTICLES = 5000

from university_regions import match_universities, reclassify_article
from article_dedup import deduplicate
from article_links import resolve_newsroom_link
from article_categories import classify_category
from rss_searches import build_search_plan, select_search_batch
from classification_monitor import build_report


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, value):
        self.parts.append(value)


def clean(value):
    parser = PlainText()
    parser.feed(unescape(value or ''))
    return ' '.join(' '.join(parser.parts).split())


def tag_name(node):
    return node.tag.rsplit('}', 1)[-1].lower()


def field(node, *names):
    for child in node:
        if tag_name(child) in names:
            return ''.join(child.itertext()).strip()
    return ''


def parse_date(value, default_offset=None):
    if not value:
        return ''
    try:
        try:
            stamp = parsedate_to_datetime(value)
        except (ValueError, TypeError):
            stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            if not default_offset:
                return ''
            stamp = datetime.fromisoformat(stamp.isoformat() + default_offset)
        return stamp.astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError, OverflowError):
        return ''


def classify(title, summary):
    text = title + ' ' + summary
    matches = match_universities(text)
    if not matches and not any(word in text for word in ('대학교', '대학', '대입', '캠퍼스')):
        return None
    regions = sorted({region for _, values in matches for region in values})
    category = classify_category(title,summary)
    return matches, regions, category


def parse_feed(raw, source, default_offset=None):
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('DTD is not supported')
    root = ET.fromstring(raw)
    if tag_name(root) not in ('rss', 'feed', 'rdf'):
        raise ValueError('Not an RSS or Atom feed')
    rows = []
    for item in root.iter():
        if tag_name(item) not in ('item', 'entry'):
            continue
        title = clean(field(item, 'title'))
        body = clean(field(item, 'description', 'summary', 'content', 'encoded'))[:500]
        match = classify(title, body)
        if not title or match is None:
            continue
        link = field(item, 'link')
        for child in item:
            if tag_name(child) == 'link' and child.get('href') and child.get('rel', 'alternate') == 'alternate':
                link = child.get('href')
                break
        if urlsplit(link).scheme not in ('http', 'https') or not urlsplit(link).netloc:
            continue
        google = urlsplit(link).hostname == 'news.google.com'
        publisher = clean(field(item, 'source')) if google else source
        if google and publisher and title.endswith(' - ' + publisher):
            title = title[:-len(' - ' + publisher)]
        if google:
            # 구글 RSS description은 요약 대신 제목과 출처를 반복합니다.
            body = '구글 뉴스에서 수집한 기사입니다. 기사 내용을 확인하려면 기사 보기 버튼을 눌러 주세요.'
        matches, regions, category = match
        rows.append(reclassify_article(dict(
            id=hashlib.sha256(link.encode()).hexdigest()[:24],
            title=title, body=body, url=link, source=publisher or source,
            feed_source=source, via_google=google,
            school=' · '.join(name for name, _ in matches) or '대학 일반',
            regions=regions, region=regions[0] if len(regions) == 1 else '',
            city=' · '.join(regions) or '지역 미분류', mark='N', category=category,
            date=parse_date(field(item, 'pubdate', 'published', 'date', 'updated'), default_offset),
        )))
    return rows


class Collector:
    def __init__(self):
        self.lock = threading.Lock()
        self.news = []
        self.raw_news = []
        self.search_cursor = 0
        self.status = dict(state='collecting', lastSuccess=None, errors=[], sources=[])
        try:
            cached = json.loads(CACHE.read_text(encoding='utf-8'))
            self.raw_news = [reclassify_article(item) for item in cached.get('raw_news',cached['news'])]
            unique_news = deduplicate(self.raw_news)
            self.news = unique_news[:MAX_ARTICLES]
            self.status['duplicates_removed'] = len(self.raw_news)-len(unique_news)
            self.status['lastSuccess'] = cached.get('lastSuccess')
            self.search_cursor = cached.get('search_cursor',0)
        except (OSError, ValueError, KeyError):
            pass

    def snapshot(self):
        with self.lock:
            # 다른 수집 실행에서 보완된 날짜도 실행 중인 화면에 반영합니다.
            try:
                cached = json.loads(CACHE.read_text(encoding='utf-8'))
                by_id = {item['id']: item for item in cached['news']}
                self.news = [dict(item, date=by_id[item['id']]['date'])
                             if not item.get('date') and by_id.get(item['id'], {}).get('date')
                             else item for item in self.news]
            except (OSError, ValueError, KeyError, TypeError):
                pass
            return list(self.news), dict(self.status)

    def refresh(self):
        errors, received, statuses = [], [], []
        try:
            sources = json.loads((ROOT / 'rss_sources.json').read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            with self.lock:
                self.status.update(state='error', errors=[f'RSS 설정: {exc}'])
            return
        config_path=ROOT/'rss_search_config.json'
        try:
            config=json.loads(config_path.read_text(encoding='utf-8')) if config_path.exists() else {}
            plan=build_search_plan(config)
            batch,next_cursor=select_search_batch(plan,self.search_cursor,config.get('feeds_per_cycle',30))
            sources.extend(batch)
            gap=max(0.1,min(float(config.get('request_gap_seconds',0.35)),3))
        except (OSError,ValueError,TypeError) as exc:
            errors.append(f'확장 검색 설정: {exc}')
            plan,batch,next_cursor,gap=[],[],self.search_cursor,0.35
        with self.lock:
            self.status.update(state='collecting',search_plan_total=len(plan),search_batch_size=len(batch),search_completed=0)
        successes = 0
        expanded_statuses=[]
        for source in sources:
            throttled=False
            if not source.get('enabled', True):
                continue
            name = source.get('name', 'RSS')
            try:
                url = source['url']
                if urlsplit(url).scheme not in ('http', 'https'):
                    raise ValueError('Only HTTP(S) feeds are supported')
                request = Request(url, headers={'User-Agent': 'CampusOnRSS/1.0 (personal RSS reader)'})
                with urlopen(request, timeout=12) as response:
                    raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise ValueError('Feed exceeds 2 MB')
                items = parse_feed(raw, name, source.get('timezone_offset'))
                # 검색 결과의 홈페이지 경유 대신 제목이 일치하는 뉴스룸 상세 주소를 보완합니다.
                items = [resolve_newsroom_link(item) for item in items]
                received.extend(items)
                successes += 1
                total = sum(1 for node in ET.fromstring(raw).iter() if tag_name(node) in ('item', 'entry'))
                statuses.append(dict(name=name, total=total, count=len(items), ok=True))
            except Exception as exc:
                errors.append(f'{name}: {type(exc).__name__}: {exc}')
                statuses.append(dict(name=name, count=0, ok=False))
                throttled=getattr(exc,'code',None) in (429,503)
            if source.get('expanded'):
                expanded_statuses.append(statuses.pop())
                with self.lock:self.status['search_completed']=len(expanded_statuses)
                time.sleep(gap)
            if throttled:
                errors.append('요청 제한 또는 일시 중단 응답으로 이번 회차의 남은 검색을 보류했습니다.')
                next_cursor=(self.search_cursor+len(expanded_statuses))%len(plan) if plan else self.search_cursor
                break
        if expanded_statuses:
            statuses.append(dict(name=f'지역·대학별 확장 검색 {len(expanded_statuses)}개',
                                 total=sum(s.get('total',0) for s in expanded_statuses),count=sum(s['count'] for s in expanded_statuses),
                                 ok=any(s['ok'] for s in expanded_statuses)))
        with self.lock:
            merged = {item['id']: item for item in self.raw_news}
            known_ids=set(merged)
            observed=[]
            seen_at=datetime.now(timezone.utc).isoformat()
            for item in received:
                previous = merged.get(item['id'])
                if previous and previous.get('original_url') and not item.get('original_url'):
                    item = dict(item, original_url=previous['original_url'])
                if previous and previous.get('date') and not item.get('date'):
                    item = dict(item, date=previous['date'])
                item=dict(item,first_seen=previous.get('first_seen',seen_at) if previous else seen_at,last_seen=seen_at)
                merged[item['id']] = item
                observed.append(item)
            classification_report=build_report(observed,known_ids)
            self.status['classification_check']={key:classification_report[key] for key in ('checked_at','checked_count','new_count','updated_count','error_count','review_count')}
            self.raw_news = sorted(merged.values(), key=lambda n: n['date'], reverse=True)[:MAX_ARTICLES*3]
            unique_news = deduplicate(self.raw_news)
            self.news = unique_news[:MAX_ARTICLES]
            if successes:
                self.status['lastSuccess'] = datetime.now(timezone.utc).isoformat()
            self.status.update(state='partial' if successes and errors else 'ready' if successes else 'error', errors=errors, sources=statuses)
            self.status['duplicates_removed'] = len(self.raw_news)-len(unique_news)
            self.search_cursor=next_cursor
            self.status.update(search_next_cursor=next_cursor,search_plan_total=len(plan),search_batch_size=len(batch))
            cached = dict(news=self.news, raw_news=self.raw_news, lastSuccess=self.status['lastSuccess'],search_cursor=self.search_cursor)
        if successes:
            try:
                temporary = CACHE.with_suffix('.tmp')
                temporary.write_text(json.dumps(cached, ensure_ascii=False), encoding='utf-8')
                temporary.replace(CACHE)
                monitor_path=ROOT/'classification_monitor_report.json'
                monitor_tmp=monitor_path.with_suffix('.tmp')
                monitor_tmp.write_text(json.dumps(classification_report,ensure_ascii=False,indent=2),encoding='utf-8')
                monitor_tmp.replace(monitor_path)
            except OSError:
                with self.lock:
                    self.status['errors'].append('수집 결과를 디스크에 저장하지 못했습니다.')

    def start(self, stop):
        def worker():
            previous_config = None
            next_refresh = 0
            import time
            while not stop.is_set():
                try:
                    config = tuple(path.stat().st_mtime_ns if path.exists() else None for path in [ROOT/'rss_sources.json',ROOT/'rss_search_config.json'])
                except OSError:
                    config = None
                if config != previous_config or time.monotonic() >= next_refresh:
                    self.refresh()
                    previous_config = config
                    next_refresh = time.monotonic() + INTERVAL
                stop.wait(5)
        threading.Thread(target=worker, daemon=True, name='rss-collector').start()
