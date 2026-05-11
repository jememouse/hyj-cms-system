import sys
import os
import json
from collections import defaultdict

sys.path.insert(0, "/Users/wang/code-project/hyj_AI-auto-cms-system")
from shared.google_client import GoogleSheetClient
from shared import config

client = GoogleSheetClient()

ASSETS_FILE = "/Users/wang/code-project/hyj_AI-auto-cms-system/published_assets.json"
counts = defaultdict(int)

if os.path.exists(ASSETS_FILE):
    with open(ASSETS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        for item in data:
            date_str = item.get("published_at", "")[:10]
            if date_str:
                counts[date_str] += 1

sorted_dates = sorted(counts.keys())
lines = ["📊 历史每日发布统计："]
total = 0
for d in sorted_dates:
    lines.append(f" - {d}: {counts[d]} 篇")
    total += counts[d]
lines.append(f"\n总计发布: {total} 篇")

content = "\n".join(lines)
print(content)
client.send_notification("每日发布数据统计", content)
