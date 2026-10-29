import json
from pathlib import Path

from rss_collector import Collector

root = Path(__file__).resolve().parent

# 이전에 저장된 뉴스 데이터를 RSS 캐시로 복원
news_path = root / "news.json"
cache_path = root / ".rss-cache.json"

if news_path.exists():
    previous = json.loads(news_path.read_text(encoding="utf-8"))

    if isinstance(previous.get("news"), list):
        cache_path.write_text(
            json.dumps(
                {
                    "news": previous["news"],
                    "raw_news": previous["news"],
                    "lastSuccess": previous.get("status", {}).get("lastSuccess"),
                    "search_cursor": previous.get("search_cursor", 0),
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

collector = Collector()
collector.refresh()

news, status = collector.snapshot()

if status["state"] == "error":
    raise RuntimeError("RSS 수집에 실패했습니다.")

if not news:
    raise RuntimeError("수집된 뉴스가 없습니다.")

output = root / "news.json"
output.write_text(
    json.dumps(
        {"news": news, "status": status},
        ensure_ascii=False
    ),
    encoding="utf-8"
)

print(f"news.json 갱신 완료: {len(news)}건")
