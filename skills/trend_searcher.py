import sys
import os
import requests
import re
import json
import time
import logging
from datetime import datetime
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.skill import BaseSkill
from shared import config

# 加载 .env 环境变量
load_dotenv()

# 配置 logger
logger = logging.getLogger(__name__)

class TrendSearchSkill(BaseSkill):
    """
    技能: 全网热点挖掘 (Baidu, Weibo, Toutiao, etc.)
    """
    def __init__(self):
        super().__init__(
            name="trend_search",
            description="从百度、微博、头条、知乎、小红书等平台抓取热门话题"
        )
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Cookie": "SUB=_2AkMSb-1af8NxqwJRmP0SzGvmZY1yyA_EieKkA3HJJRMxHRl-yT9kqmsstRB6POKqfE_JzXqqfE_JzXqqfE_JzXqq;" 
        }

    def execute(self, input_data: dict) -> list:
        """
        Input: {"mining_seeds": ["seed1", ...]}
        Output: ["raw_trend_1", "raw_trend_2", ...]
        """
        mining_seeds = input_data.get("mining_seeds", [])
        all_trends = []

        print("📡 [TrendSearch] 开始多源数据抓取...")
        
        # ===== 0. 提取云端(Google Sheets: keywords_lib)的优先级词条 (如 5118 导出) =====
        try:
            from shared.google_client import GoogleSheetClient
            client = GoogleSheetClient()
            if client.client: # 确认连接成功
                print("📦 正在连接 Google Sheets 读取 `keywords_lib` 蓄水池...")
                pull_limit = 30
                
                # 兼容两种状态：留空 ("") 或者填了 "Unused"
                unused_records = client.fetch_records_by_status("", limit=pull_limit, table_id="keywords_lib")
                if len(unused_records) < pull_limit:
                    unused_records.extend(client.fetch_records_by_status("Unused", limit=pull_limit - len(unused_records), table_id="keywords_lib"))
                    
                externals = []
                if unused_records:
                    for r in unused_records:
                        kw = str(r.get("Keyword", "")).strip()
                        if kw:
                            externals.append(f"[外部指定] {kw}")
                            # 立即标记该单元格为 Used 并填入使用时间，完成滴灌闭环
                            rec_id = r.get("record_id")
                            if rec_id:
                                import time
                                now_str = time.strftime("%Y-%m-%d %H:%M:%S")
                                client.update_record(rec_id, {
                                    "Status": "Used",
                                    "词条使用时间": now_str
                                }, table_id="keywords_lib")
                    
                    if externals:
                        all_trends.extend(externals)
                        print(f"✅ 成功从云端蓄水池滴灌了 {len(externals)} 个高优词条到本批次")
                else:
                    print("ℹ️ 蓄水池 (keywords_lib) 中目前没有待处理的 Unused 词条。")
        except Exception as e:
            import traceback
            print(f"❌ 读取云端词库表异常: {e}")
            traceback.print_exc()

        # ===== 1. 种子词轮换策略 (保持话题多样性) =====
        if mining_seeds:
            mining_seeds = self._rotate_seeds(mining_seeds)
        
        # 1. 挖掘长尾需求
        if mining_seeds:
            all_trends.extend(self._fetch_baidu_suggestions(mining_seeds))
            all_trends.extend(self._fetch_1688_suggestions(mining_seeds))
            all_trends.extend(self._fetch_taobao_suggestions(mining_seeds))
            all_trends.extend(self._fetch_zhihu_hot_questions(mining_seeds))
            all_trends.extend(self._fetch_xiaohongshu_trends(mining_seeds))
            all_trends.extend(self._fetch_google_trends(mining_seeds))

        # 2. 抓取平台热榜
        for t in self._fetch_baidu_hot():
            all_trends.append(f"[百度] {t}")
        for t in self._fetch_weibo_hot():
            all_trends.append(f"[微博] {t}")
        for t in self._fetch_toutiao_hot():
            all_trends.append(f"[头条] {t}")
        for t in self._fetch_36kr_hot():
            all_trends.append(f"[36氪] {t}")

        # 去重
        unique_trends = list(set(all_trends))
        print(f"📊 [TrendSearch] 共收集到 {len(unique_trends)} 个唯一热点话题")
        return unique_trends

    # --- Internal Fetch Methods (Moved from fetch_trends.py) ---

    def _rotate_seeds(self, seeds: list) -> list:
        """
        基于日期的种子词轮换，保持话题多样性
        每天使用不同的种子词组合，避免内容同质化
        """
        import random
        from datetime import datetime
        
        # 定义种子词分类 (基于关键词匹配)
        SEED_GROUPS = {
            "产品类": ["礼盒", "纸箱", "飞机盒", "手提袋", "包装盒", "纸盒", "彩盒", "内托", "内衬"],
            "工艺类": ["烫金", "UV", "覆膜", "击凸", "印刷", "模切", "制版"],
            "行业趋势": ["国潮", "极简", "智能", "可降解", "碳中和", "数字化", "AI", "趋势"],
            "展会活动": ["展", "会", "峰会", "论坛", "大赛"],
            "通用转化": ["定制", "厂家", "批发", "源头", "直销", "免费", "报价"]
        }
        
        # 按日期选择主力分组 (0=周一, 6=周日)
        weekday = datetime.now().weekday()
        group_schedule = ["产品类", "工艺类", "行业趋势", "展会活动", "通用转化", "产品类", "行业趋势"]
        primary_group = group_schedule[weekday]
        
        # 分类种子词
        categorized = {k: [] for k in SEED_GROUPS}
        uncategorized = []
        
        for seed in seeds:
            matched = False
            for group, keywords in SEED_GROUPS.items():
                if any(kw in seed for kw in keywords):
                    categorized[group].append(seed)
                    matched = True
                    break
            if not matched:
                uncategorized.append(seed)
        
        # 构建今日种子组合: 主力组50% + 其他组各10% + 未分类20%
        result = []
        
        # 主力组 (最多30个)
        primary_seeds = categorized.get(primary_group, [])
        result.extend(random.sample(primary_seeds, min(30, len(primary_seeds))))
        
        # 其他组各取5个
        for group, group_seeds in categorized.items():
            if group != primary_group and group_seeds:
                result.extend(random.sample(group_seeds, min(5, len(group_seeds))))
        
        # 未分类取10个
        if uncategorized:
            result.extend(random.sample(uncategorized, min(10, len(uncategorized))))
        
        # 打乱顺序
        random.shuffle(result)
        
        print(f"🔄 [SeedRotation] 今日主力: {primary_group} | 种子数: {len(result)} (原{len(seeds)})")
        return result

    def _fetch_baidu_hot(self):
        try:
            resp = requests.get("https://top.baidu.com/board?tab=realtime", headers=self.headers, timeout=10)
            resp.encoding = 'utf-8'
            titles = re.findall(r'<div class="c-single-text-ellipsis">\s*(.*?)\s*</div>', resp.text)
            return [t.strip() for t in titles if t.strip() and "置顶" not in t][:15]
        except Exception as e:
            print(f"   ❌ [Baidu] 失败: {e}")
            return []

    def _fetch_weibo_hot(self):
        try:
            resp = requests.get("https://s.weibo.com/top/summary", headers=self.headers, timeout=10)
            titles = re.findall(r'<a href="/weibo\?q=[^"]+" target="_blank">([^<]+)</a>', resp.text)
            return [t.strip() for t in titles if t.strip()][:15]
        except Exception as e:
            print(f"   ❌ [Weibo] 失败: {e}")
            return []

    def _fetch_toutiao_hot(self):
        try:
            resp = requests.get("https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc", headers=self.headers, timeout=10)
            data = resp.json()
            titles = []
            if "fixed_top_data" in data:
                titles.extend([i.get("Title") for i in data["fixed_top_data"]])
            if "data" in data:
                titles.extend([i.get("Title") for i in data["data"]])
            return titles[:15]
        except Exception as e:
            print(f"   ❌ [Toutiao] 失败: {e}")
            return []

    def _fetch_36kr_hot(self):
        try:
            resp = requests.get("https://36kr.com/newsflashes", headers=self.headers, timeout=10)
            html = resp.text
            start_marker = "window.initialState="
            if start_marker in html:
                start_idx = html.find(start_marker) + len(start_marker)
                end_idx = html.find("</script>", start_idx)
                json_str = html[start_idx:end_idx].strip().rstrip(";")
                data = json.loads(json_str)
                items = data.get("newsflashCatalogData", {}).get("data", {}).get("newsflashList", {}).get("data", {}).get("itemList", [])
                titles = []
                for item in items:
                    t = item.get("templateMaterial", {}).get("widgetTitle")
                    if t: titles.append(t)
                return titles[:15]
            return []
        except Exception as e:
            print(f"   ❌ [36Kr] 失败: {e}")
            return []

    def _fetch_baidu_suggestions(self, seeds):
        suggestions = []
        for seed in seeds:
            try:
                url = f"http://suggestion.baidu.com/su?wd={seed}&p=3&cb=window.bdsug.sug"
                resp = requests.get(url, headers=self.headers, timeout=5)
                match = re.search(r's:(\[.*?\])', resp.text)
                if match:
                    words = json.loads(match.group(1).replace("'", '"'))[:5]
                    suggestions.extend([f"[搜索需求] {w}" for w in words])
            except Exception as e:
                logger.debug(f"[百度建议] {seed} 抓取失败: {e}")
        return suggestions

    def _fetch_1688_suggestions(self, seeds):
        suggestions = []
        import random
        for seed in random.sample(seeds, min(10, len(seeds))):
             try:
                url = f"https://suggest.1688.com/bin/suggest?code=utf-8&q={seed}"
                resp = requests.get(url, headers=self.headers, timeout=5)
                data = resp.json()
                if "result" in data:
                    suggestions.extend([f"[1688采购] {i['q']}" for i in data['result'][:5]])
             except Exception as e:
                logger.debug(f"[1688建议] {seed} 抓取失败: {e}")
        return suggestions

    def _fetch_taobao_suggestions(self, seeds):
        suggestions = []
        import random
        for seed in random.sample(seeds, min(10, len(seeds))):
            try:
                url = f"https://suggest.taobao.com/sug?code=utf-8&q={seed}&k=1&area=c2c"
                resp = requests.get(url, headers=self.headers, timeout=5)
                data = resp.json()
                if "result" in data:
                    suggestions.extend([f"[淘宝热搜] {i[0]}" for i in data['result'][:5]])
            except Exception as e:
                logger.debug(f"[淘宝建议] {seed} 抓取失败: {e}")
        return suggestions
    
    def _fetch_zhihu_hot_questions(self, seeds):
        questions = []
        import random
        for seed in random.sample(seeds, min(8, len(seeds))):
            try:
                url = f"https://www.zhihu.com/api/v4/search_v3?t=general&q={seed}&offset=0&limit=5"
                headers = {**self.headers, "Referer": "https://www.zhihu.com/search"}
                resp = requests.get(url, headers=headers, timeout=8)
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("data", [])[:3]:
                        if item.get("type") == "search_result":
                            obj = item.get("object", {})
                            title = obj.get("title", "") or obj.get("question", {}).get("title", "")
                            if title:
                                clean = re.sub(r'<[^>]+>', '', title)
                                questions.append(f"[知乎问答] {clean}")
            except Exception as e:
                logger.debug(f"[知乎问答] {seed} 抓取失败: {e}")
        return list(set(questions))

    def _fetch_xiaohongshu_trends(self, seeds):
        trends = []
        import random
        for seed in random.sample(seeds, min(6, len(seeds))):
            try:
                url = f"https://edith.xiaohongshu.com/api/sns/web/v1/search/hot_list"
                headers = {**self.headers, "Referer": "https://www.xiaohongshu.com/"}
                resp = requests.get(url, headers=headers, timeout=8)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success"):
                        for item in data["data"].get("list", [])[:10]:
                            if any(k in item.get("title", "") for k in ["包装","礼盒","送礼"]):
                                trends.append(f"[小红书] {item['title']}")
                        break
            except Exception as e:
                logger.debug(f"[小红书] {seed} 抓取失败: {e}")
        
        scenes = ["开箱体验","送礼推荐","高级感包装"]
        for seed in random.sample(seeds, min(3, len(seeds))):
            for s in random.sample(scenes, 2):
                trends.append(f"[小红书] {seed}{s}")
        return list(set(trends))

    def _fetch_google_trends(self, seeds):
        trends = []
        keywords = ["custom packaging", "gift box wholesale", "mailer box"]
        for kw in keywords:
            try:
                url = f"https://trends.google.com/trends/api/autocomplete/{kw.replace(' ', '%20')}?hl=en-US"
                resp = requests.get(url, headers={"User-Agent": self.headers["User-Agent"]}, timeout=8)
                text = resp.text[5:] if resp.text.startswith(")]}'") else resp.text
                data = json.loads(text)
                for t in data.get("default", {}).get("topics", [])[:3]:
                    trends.append(f"[谷歌趋势] {t['title']}")
            except Exception as e:
                logger.debug(f"[谷歌趋势] {kw} 抓取失败: {e}")
        return list(set(trends))
