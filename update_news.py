import json
from pathlib import Path

from rss_collector import Collector

root = Path(__file__).resolve().parent

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
