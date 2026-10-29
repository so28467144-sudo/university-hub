"""실행: python app.py --open (Python 3.9+, 추가 패키지 불필요)."""
import argparse
import json
import runpy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from urllib.parse import urlsplit
import webbrowser
from rss_collector import Collector, MAX_ARTICLES
from excel_export import make_workbook

ROOT = Path(__file__).resolve().parent
ASSETS = {'/app.js': ('app.js', 'text/javascript'), '/style.css': ('style.css', 'text/css')}
collector = Collector()


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if urlsplit(self.path).path != '/export.xlsx':
            self.send_error(404)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_ARTICLES * 100:
                raise ValueError('Invalid request size')
            ids = json.loads(self.rfile.read(length)).get('ids')
            if not isinstance(ids, list) or len(ids)>MAX_ARTICLES or not all(isinstance(value,str) for value in ids):
                raise ValueError('Invalid article selection')
        except (ValueError, TypeError, AttributeError):
            self.send_error(400)
            return
        news, _ = collector.snapshot()
        by_id = {item['id']: item for item in news}
        if any(value not in by_id for value in ids):
            self.send_error(409, 'Article list changed; refresh and retry')
            return
        body = make_workbook([by_id[value] for value in dict.fromkeys(ids)])
        self.send_response(200)
        self.send_header('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.send_header('Content-Disposition', 'attachment; filename="campus-news.xlsx"')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in ('/', '/index.html'):
            # 개발 중 data.py를 수정하면 서버 재시작 없이 반영합니다.
            data = runpy.run_path(str(ROOT / 'data.py'))
            news, status = collector.snapshot()
            payload = json.dumps(dict(regions=data['REGIONS'], categories=data['CATEGORIES'] + ['대학 소식'], news=news, status=status), ensure_ascii=False)
            # Escape '<' to keep the embedded JSON inside its script element.
            payload = payload.replace('<', '\\u003c')
            bootstrap = '<script>window.CAMPUS_DATA=' + payload + ';</script>'
            page = (ROOT / 'index.html').read_text(encoding='utf-8')
            page = page.replace('<script src="app.js" defer></script>', bootstrap + '<script src="app.js" defer></script>')
            self.respond(page.encode('utf-8'), 'text/html')
        elif path == '/news.json':
            news, status = collector.snapshot()
            self.respond(json.dumps(dict(news=news, status=status), ensure_ascii=False).encode('utf-8'), 'application/json')
        elif path in ASSETS:
            filename, content_type = ASSETS[path]
            self.respond((ROOT / filename).read_bytes(), content_type)
        elif path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
        else:
            self.send_error(404)

    def respond(self, body, content_type):
        self.send_response(200)
        self.send_header('Content-Type', content_type + '; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description='Campus On local Python website')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--open', action='store_true', help='Open the website in your browser')
    args = parser.parse_args()
    try:
        server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    except OSError as exc:
        parser.exit(1, f'Cannot start server: {exc}\nTry --port 8001\n')
    url = f'http://127.0.0.1:{server.server_port}'
    print(f'Campus On: {url}\nPress Ctrl+C to stop.', flush=True)
    stop = threading.Event()
    collector.start(stop)
    if args.open:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()


if __name__ == '__main__':
    main()
