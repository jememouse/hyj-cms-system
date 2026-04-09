from core.state_bus import StateBus
import json
bus = StateBus()
records = bus.client.fetch_records_by_status("Pending")
if not records:
    records = bus.client.fetch_records_by_status("Top priority pending")
if not records:
    records = bus.client.fetch_records_by_status("Published", limit=2)
for rec in records[:1]:
    summary = rec.get("摘要")
    one_line = rec.get("One_Line_Summary")
    tags = rec.get("Tags")
    print(f"TITLE: {rec.get('Title')[:50]}")
    print(f"SUMMARY: {summary}")
    print(f"ONE_LINE: {one_line}")
    print(f"TAGS: {tags}")
