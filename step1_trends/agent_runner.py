import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.trend_hunter import TrendHunterAgent

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(BASE_DIR, 'box_artist_config.json')
OUTPUT_FILE = os.path.join(BASE_DIR, 'generated_seo_data.json')

def run():
    print("\n" + "=" * 50)
    print("🤖 启动 Agentic Workflow (Step 1: Trend Hunting)")
    print("=" * 50 + "\n")
    
    # Load Config
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            args = json.load(f)
    else:
        args = {"mining_seeds": ["包装", "礼盒"]}
    hunter = TrendHunterAgent()
    topics = hunter.hunt_and_analyze(args)
    
    if topics:
        from shared import config
        # 根据产生结果来源判断状态，外部导入词汇赋予最高插队权 Priority
        for t in topics:
            if '[外部指定]' in t.get('Source_Trend', ''):
                t['Status'] = config.STATUS_PRIORITY
            else:
                t['Status'] = config.STATUS_READY
        # Save results
        # Save results (Append Mode)
        existing_data = []
        if os.path.exists(OUTPUT_FILE):
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                try:
                    existing_data = json.load(f)
                except json.JSONDecodeError:
                    pass

        # Avoid duplicates (check by Topic name)
        existing_topics = {item['Topic'] for item in existing_data}
        new_count = 0
        for t in topics:
            if t['Topic'] not in existing_topics:
                existing_data.append(t)
                new_count += 1
        
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)
            
        print(f"💾 结果已保存至 {OUTPUT_FILE} (新增 {new_count} 条, 总计 {len(existing_data)} 条)")
        print(f"💾 结果已保存至 {OUTPUT_FILE}")

        # Sync to Feishu (For Github Actions Persistence)
        if new_count > 0:
            print(f"☁️ 正在同步 {new_count} 条新选题到飞书...")
            try:
                from shared.google_client import GoogleSheetClient
                from shared import config
                
                client = GoogleSheetClient()
                
                # Check duplicates in Feishu (This is expensive, so we just try batch create and ignore errors or rely on Feishu logic? 
                # Better: only upload what we determined as new locally)
                
                # Filter 'topics' to only include the ones we just added to existing_data
                # But 'topics' is the list of *newly generated* ones.
                # Among them, we filtered some out if they were in existing_data *before*.
                # Let's filter topics again to match the ones we appended.
                
                upload_list = []
                for t in topics:
                    # Check if this t was added. 
                    # We can re-use the logic: if t['Topic'] was not in existing_topics BEFORE update.
                    if t['Topic'] not in existing_topics:
                        # Ensure we have a timestamp
                        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
                        record = {
                            "Topic": t['Topic'],
                            "大项分类": t['大项分类'],
                            "Status": t['Status'], # 原为 config.STATUS_READY，现改为动态传递 Priority 或 Ready
                            "Source_Trend": t.get('Source_Trend', ''),
                            "选题生成时间": t.get('created_at') or now_str # Handle empty string or missing key
                        }
                        upload_list.append(record)
                
                if upload_list:
                    success = client.batch_create_records(upload_list)
                    if success:
                        print(f"✅ 已同步 {len(upload_list)} 条记录到飞书")
                else:
                    print("⚠️ 没有新选题需要同步")
                    
            except Exception as e:
                print(f"❌ 飞书同步失败: {e}")

if __name__ == "__main__":
    run()
