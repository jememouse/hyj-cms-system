import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.chief_editor import ChiefEditorAgent
from shared.google_client import GoogleSheetClient
from shared import config

def run():
    print("\n" + "=" * 50)
    print("🤖 启动 Agentic Workflow (Step 2: Article Gen)")
    print("=" * 50 + "\n")
    
    # Init
    editor = ChiefEditorAgent()
    client = GoogleSheetClient()
    
    # Load Topics (From Feishu for Persistence)
    print("☁️ 正在从 Google Sheets 拉取待生成的选题...")
    
    # 拉取 Priority 状态的特权选题
    priority_topics = client.fetch_records_by_status(config.STATUS_PRIORITY, limit=100, sort_by_time_col="选题生成时间", reverse_batch=False)
    
    # 拉取 Ready 状态的常规选题
    ready_topics = client.fetch_records_by_status(config.STATUS_READY, limit=500, sort_by_time_col="选题生成时间", reverse_batch=False)
    
    pending_topics = priority_topics + ready_topics
    
    if not pending_topics:
        print("❌ 表格中没有找到 Priority 或 Ready 状态的选题，请先运行 Step 1")
        return

    print(f"📋 从表格获取到 {len(priority_topics)} 个特权选题及 {len(ready_topics)} 个常规选题")
    
    # Load Config Limit
    max_total_limit = config.STEP2_STRATEGY.get("max_generate_total", 100)
    print(f"⚙️  总处理上限 (所有分类合计): {max_total_limit}")

    # 3. 分组与 Round-Robin 排序 (仅针对常规 Ready 选题)
    # Group by Category
    from collections import defaultdict
    grouped_topics = defaultdict(list)
    for t in ready_topics:
        
        # Ensure keys exist
        if 'Topic' not in t:
            t['Topic'] = t.get('topic', '') # Fallback
            
        if '大项分类' not in t:
             t['大项分类'] = t.get('category', '未分类')

        cat = t.get('大项分类', '未分类')
        grouped_topics[cat].append(t)
    
    print("📊 常规待处理选题分布:")
    for cat, items in grouped_topics.items():
        print(f"   - {cat}: {len(items)} 条")
        
    # 构建最终待执行的 sorted_topics
    sorted_topics = []
    
    # (1) Priority 选题直接插队 (不经过 Round-Robin)
    for t in priority_topics:
        sorted_topics.append(t)
        
    # (2) 常规选题进行 Round-Robin Merge
    from itertools import zip_longest
    # We want to merge the categories evenly. 
    # Grab all items from each category instead of slicing by per_category limit
    lists = list(grouped_topics.values())
    
    for items in zip_longest(*lists):
        for item in items:
            if item is not None:
                sorted_topics.append(item)
                
    # 严格按照总上限进行切割 (特权选题依然排在最前面占额度)
    sorted_topics = sorted_topics[:max_total_limit]
                
    print(f"🔄 排序(头部特权排队+普通均衡)后共取 {len(sorted_topics)} 条任务准备执行")
    
    import random
    from datetime import datetime
    
    # 4. Execute
    for idx, item in enumerate(sorted_topics):
        print(f"\n--- [{idx + 1}/{len(sorted_topics)}] {item['大项分类']} | {item['Topic'][:30]}... ---")
        
        # [Newsjacking] Try to get source trend for context injection
        source_trend = item.get('Source_Trend', '')
        if source_trend:
            print(f"   🔥 [Newsjacking] 关联热点: {source_trend}")
            
        article = editor.write_article(item['Topic'], item['大项分类'], source_trend=source_trend)
        
        if article:
            # Update Feishu Record (Status: Ready -> Pending)
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # [Data Integrity] 强校验：确保生成的内容有效
            title = article.get('title', '').strip()
            content = article.get('html_content', '').strip()
            
            if not title or len(content) < 50:
                print(f"   ⚠️ [Error] 生成内容无效 (Title len: {len(title)}, Content len: {len(content)})")
                print(f"   🛑 跳过保存，保持 Ready 状态等待重试")
                continue
                
            # 判断是否为最高优先级文章
            is_priority = (item.get('Status') == config.STATUS_PRIORITY)
            target_status = config.STATUS_TOP_PRIORITY_PENDING if is_priority else config.STATUS_PENDING
            
            # 追加专用标签
            final_tags = article.get('tags')
            if is_priority:
                priority_tag = "Top priority"
                if not final_tags:
                    final_tags = priority_tag
                elif isinstance(final_tags, list):
                    if priority_tag not in final_tags:
                        final_tags.insert(0, priority_tag)
                else:
                    if priority_tag not in str(final_tags):
                        final_tags = f"{priority_tag}, {final_tags}"

            # Fields to update
            fields = {
                "Title": title,
                "HTML_Content": content,
                "Status": target_status,
                "关键词": article.get('keywords'),
                "摘要": article.get('summary'),
                "描述": article.get('description'),
                "Tags": final_tags,
                "生成时间": current_time,
                # [Fix Zombie State] 重生成时必须清除旧的发布信息
                "URL": "",
                "发布时间": "", 
                # "选题生成时间": item.get('created_at', ''), # Retain original value
                "One_Line_Summary": article.get('one_line_summary', ''),
                "Schema_FAQ": json.dumps(article.get('schema_faq', []), ensure_ascii=False),
                "Key_Points": json.dumps(article.get('key_points', []), ensure_ascii=False)
            }
            
            # Check if we have record_id (From Feishu Fetch)
            record_id = item.get('record_id')
            if record_id:
                success = client.update_record(record_id, fields)
                if success:
                    print(f"   💾 已在飞书更新记录 (ID: {record_id}, Status: Pending)")
            else:
                # Fallback: Create new (Should not happen in new flow)
                client.create_record(fields)
                print("   ⚠️ 未找到 record_id，创建了新记录")
        
        # Random Interval based on strategy config
        wait_min = config.STEP2_STRATEGY.get("wait_time_min", 2.0)
        wait_max = config.STEP2_STRATEGY.get("wait_time_max", 4.0)
        wait_time = random.uniform(wait_min, wait_max)
        print(f"   ⏳ 等待 {wait_time:.1f} 秒...")
        time.sleep(wait_time)

if __name__ == "__main__":
    run()
