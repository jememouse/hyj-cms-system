'''
Author: jememouse jememouse@gmail.com
Date: 2026-05-11 16:05:13
LastEditors: jememouse jememouse@gmail.com
LastEditTime: 2026-05-11 16:05:17
FilePath: /hyj_AI-auto-cms-system/scripts/daily_report.py
Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
'''
import sys
import os
import json
from collections import defaultdict
from datetime import datetime, timedelta

# 动态添加项目根目录到 sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from shared.google_client import GoogleSheetClient
from shared import config

def generate_daily_report():
    print("📊 开始生成每日发布数据统计报告...")
    
    client = GoogleSheetClient()
    assets_file = os.path.join(PROJECT_ROOT, "published_assets.json")
    
    counts = defaultdict(int)
    total_published = 0
    
    if os.path.exists(assets_file):
        try:
            with open(assets_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data:
                    date_str = item.get("published_at", "")[:10]
                    if date_str:
                        counts[date_str] += 1
                        total_published += 1
        except Exception as e:
            print(f"⚠️ 读取 published_assets.json 失败: {e}")
            return
    else:
        print(f"⚠️ 未找到文件: {assets_file}")
        return
        
    # 获取今天和昨天的日期
    today_str = datetime.now().strftime("%Y-%m-%d")
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    today_count = counts.get(today_str, 0)
    yesterday_count = counts.get(yesterday_str, 0)
    
    # 按照日期降序提取最近 7 天的记录
    sorted_dates = sorted(counts.keys(), reverse=True)
    recent_7_days = sorted_dates[:7]
    
    # 构建飞书消息内容
    lines = [
        f"📅 **每日发布数据统计 ({today_str})**",
        "",
        f"🌟 **今日发布**: {today_count} 篇",
        f"📈 **昨日发布**: {yesterday_count} 篇",
        f"🏆 **历史累计总发布**: {total_published} 篇",
        "",
        "**🗓️ 最近 7 天发布趋势:**"
    ]
    
    for d in recent_7_days:
        lines.append(f" - {d}: {counts[d]} 篇")
        
    lines.append("")
    lines.append("🤖 *本条消息由 AI-Auto-CMS 自动化系统每日定时发送*")
    
    content = "\n".join(lines)
    print("--------------------------------------------------")
    print(content)
    print("--------------------------------------------------")
    
    # 发送飞书通知
    success = client.send_notification("每日发布数据统计", content)
    if success:
        print("✅ 飞书通知发送成功！")
    else:
        print("❌ 飞书通知发送失败！请检查 webhook 配置。")

if __name__ == "__main__":
    generate_daily_report()
