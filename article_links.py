"""대학 뉴스룸에서 제목이 정확히 일치하는 상세 게시글만 연결합니다."""
from html.parser import HTMLParser
import re
from urllib.parse import urlencode, urljoin, urlsplit, parse_qs
from urllib.request import Request, urlopen

SEJONG_BOARD='https://www.sejong.ac.kr/news/today/sejong-prism.do'

def title_key(value):
    return re.sub(r'\W','',value).casefold()

class ArticleAnchors(HTMLParser):
    def __init__(self,title):
        super().__init__()
        self.title=title_key(title)
        self.url=''

    def handle_starttag(self,tag,attrs):
        if tag!='a':return
        attrs=dict(attrs)
        label=attrs.get('title','').removesuffix(' 자세히 보기')
        url=urljoin(SEJONG_BOARD,attrs.get('href',''))
        parts=urlsplit(url)
        query=parse_qs(parts.query)
        if (title_key(label)==self.title and parts.hostname=='www.sejong.ac.kr'
            and parts.path==urlsplit(SEJONG_BOARD).path
            and query.get('mode')==['view'] and query.get('articleNo',[''])[0].isdigit()):
            self.url=SEJONG_BOARD+'?'+urlencode(dict(mode='view',articleNo=query['articleNo'][0]))

def find_article_url(title,html):
    parser=ArticleAnchors(title)
    parser.feed(html)
    return parser.url

def resolve_newsroom_link(item):
    if item.get('original_url') or item.get('source')!='세종대학교 뉴스룸':return item
    url=SEJONG_BOARD+'?'+urlencode(dict(srSearchKey='article_title',srSearchVal=item['title']))
    try:
        with urlopen(Request(url,headers={'User-Agent':'CampusOnRSS/1.0'}),timeout=6) as response:
            html=response.read(2_000_001)
        if len(html)>2_000_000:return item
        original=find_article_url(item['title'],html.decode('utf-8'))
        if original:return dict(item,original_url=original,link_resolution='exact_newsroom_title')
    except (OSError,ValueError,UnicodeError):pass
    return item
