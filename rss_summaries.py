"""네트워크·파일 쓰기 없는 RSS 요약 선택 및 동일 ID 요약 보존."""
from html.parser import HTMLParser
from html import unescape
import re
import unicodedata
import xml.etree.ElementTree as ET

GOOGLE_NOTICE = '구글 뉴스에서 수집한 기사입니다. 기사 내용을 확인하려면 기사 보기 버튼을 눌러 주세요.'
USEFUL_KINDS = {'article_summary', 'announcement_excerpt'}
ATOM = 'http://www.w3.org/2005/Atom'
RSS = 'http://purl.org/rss/1.0/'
CONTENT = 'http://purl.org/rss/1.0/modules/content/'
SOURCE_PRIORITY = {'rss_description': 4, 'atom_summary': 4, 'rss_summary': 4,
                   'atom_content': 3, 'rss_content': 3, 'rss_content_encoded': 2,
                   'legacy_body': 1}


class SummaryText(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self.hidden = 0; self.link_depth = 0; self.link_chars = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.rsplit(':', 1)[-1]
        if tag in ('script', 'style'): self.hidden += 1
        if tag == 'a': self.link_depth += 1

    def handle_endtag(self, tag):
        tag = tag.rsplit(':', 1)[-1]
        if tag in ('script', 'style') and self.hidden: self.hidden -= 1
        if tag == 'a' and self.link_depth: self.link_depth -= 1

    def handle_data(self, data):
        if self.hidden: return
        self.parts.append(data)
        if self.link_depth: self.link_chars += len(data.strip())


def plain_summary(raw):
    parser = SummaryText(); parser.feed(unescape(raw or ''))
    text = ' '.join(' '.join(parser.parts).split())
    return text, parser.link_chars / max(len(text), 1)


def key(text):
    return re.sub(r'\W', '', unicodedata.normalize('NFKC', text)).casefold()


def assess_summary(text, title='', publisher='', link_fraction=0):
    """메타데이터의 자기 신고를 믿지 않고 본문에서 품질을 판정합니다."""
    text = text.strip(); normalized = key(text)
    if not text: return 'other', (-1, 0, 0), 'empty'
    remainder = normalized
    for repeated in (key(title), key(publisher)):
        if repeated: remainder = remainder.replace(repeated, '')
    if not remainder or link_fraction >= .70:
        return 'notice', (0, 0, 0), 'title_publisher_repeat_or_link_list'
    if text.startswith(('구글 뉴스에서 수집한 기사입니다.', '기사 내용을 확인하려면')):
        return 'notice', (0, 0, 0), 'google_notice'
    homepage_notice = '홈페이지' in text and re.search(r'참고하시기|바로가기|확인하세요', text)
    if homepage_notice:
        if len(re.findall(r'\s/\s', text)) >= 2:
            return 'announcement_excerpt', (2, 1, min(len(set(re.findall(r'\w{2,}', text))), 24)), 'recruitment_details'
        return 'notice', (0, 0, 0), 'homepage_notice'
    if re.fullmatch(r'\[인터뷰_[^\]]+\]', text):
        return 'other', (1, 1, 0), 'heading_only'
    tokens = set(re.findall(r'[가-힣A-Za-z0-9]{2,}', text))
    boilerplate = bool(re.search(r'RSS.{0,40}(?:개인|허용)|무단\s*(?:복제|재배포)|앱\s*다운로드|구글 뉴스에서 수집한 기사|기사 내용을 확인하려면', text, re.I))
    if boilerplate and (len(tokens) < 24 or re.match(r'(?:ⓒ|©|Copyright|RSS\s*피드)', text, re.I)):
        return 'notice', (0, 0, 0), 'service_notice'
    if len(text) < 15 or len(tokens) < 3:
        return 'other', (1, int(not boilerplate), len(tokens)), 'insufficient_article_text'
    # 길이보다 유용 여부·안내문 혼입·제한된 정보 다양성을 우선합니다.
    return 'article_summary', (3, int(not boilerplate), min(len(tokens), 24)), 'article_text'


def summary_fields(item):
    """알려진 RSS/Atom namespace의 텍스트 필드만 수집합니다."""
    for child in item:
        namespace, local = child.tag[1:].split('}', 1) if child.tag.startswith('{') else ('', child.tag)
        if namespace == ATOM and local in ('summary', 'content'):
            if child.get('src') or child.get('type', 'text') not in ('text', 'html', 'xhtml'): continue
            source = 'atom_' + local
        elif namespace == CONTENT and local == 'encoded': source = 'rss_content_encoded'
        elif namespace in ('', RSS) and local in ('description', 'summary', 'content'):
            source = 'rss_' + local
        else: continue  # media:content 등은 본문 필드가 아닙니다.
        raw = (child.text or '') + ''.join(ET.tostring(node, encoding='unicode') for node in child)
        yield source, raw


def select_summary(item, title, publisher='', google=False):
    candidates = []
    for source, raw in summary_fields(item):
        text, links = plain_summary(raw); text = text[:500]
        kind, quality, reason = assess_summary(text, title, publisher, links)
        candidates.append((quality + (SOURCE_PRIORITY[source],), source, text, kind, reason))
    if not candidates:
        selected = ((-1, 0, 0, 0), 'rss_missing', '', 'other', 'no_supported_text_field')
    else:
        selected = max(candidates, key=lambda row: (row[0], row[1], row[2]))
    _, source, text, kind, reason = selected
    if google and kind not in USEFUL_KINDS:
        text = GOOGLE_NOTICE; kind = 'notice'
    return dict(body=text, summary_kind=kind, summary_source=source,
                summary_selection_reason=reason)


def preserve_summary(previous, incoming):
    """같은 기사 ID의 요약만 비교하며 다른 뉴스 필드는 변경하지 않습니다."""
    result = dict(incoming)
    if previous and previous['id'] != incoming['id']: raise ValueError('Cannot merge different article IDs')
    def evaluate(item):
        text = item.get('body', '')
        kind, quality, reason = assess_summary(text, item.get('title', ''), item.get('source', ''))
        source = item.get('summary_source', 'legacy_body')
        return kind, quality + (SOURCE_PRIORITY.get(source, 1),), reason, source
    current_kind, current_quality, current_reason, current_source = evaluate(incoming)
    if previous:
        old_kind, old_quality, old_reason, old_source = evaluate(previous)
        if old_kind in USEFUL_KINDS and old_quality >= current_quality:
            result.update(body=previous.get('body', ''), summary_kind=old_kind, summary_source=old_source,
                          summary_selection_reason='retained_previous:' + old_reason)
            return result
    result.update(summary_kind=current_kind, summary_source=current_source,
                  summary_selection_reason=incoming.get('summary_selection_reason', current_reason))
    return result
