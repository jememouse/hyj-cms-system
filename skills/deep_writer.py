import sys
import os
import json
import random
import logging
from datetime import datetime
from typing import Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.skill import BaseSkill
from shared import config, llm_utils

# 配置 logger
logger = logging.getLogger(__name__)

class DeepWriteSkill(BaseSkill):
    """
    技能: 深度文章写作 (基于 PAS 模型和 GEO 优化)
    """
    def __init__(self):
        super().__init__(
            name="deep_write",
            description="根据标题撰写长篇 SEO/GEO 优化文章"
        )
        self._load_config()

    def _load_config(self):
        self.brand_config = {}
        if os.path.exists(config.CONFIG_FILE):
             with open(config.CONFIG_FILE, 'r', encoding='utf-8') as f:
                self.brand_config = json.load(f)

    def _get_dynamic_internal_links(self, count=2):
        """
        从 published_assets.json 中获取历史发布文章，供内链网络建设使用。
        """
        assets_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'published_assets.json')
        if not os.path.exists(assets_file):
            return []
        try:
            with open(assets_file, 'r', encoding='utf-8') as f:
                assets = json.load(f)
                if not assets:
                    return []
                # 随机抽取历史记录 (最多 count 条)
                sample_count = min(count, len(assets))
                return random.sample(assets, sample_count)
        except Exception as e:
            logger.error(f"[DeepWriter] 读取 published_assets.json 失败: {e}")
            return []

    def execute(self, input_data: Dict) -> Dict:
        """
        Input: {"topic": str, "category": str, "rag_context": str (optional)}
        Output: Article JSON
        """
        topic = input_data.get("topic", "")
        category = input_data.get("category", "行业资讯")
        source_trend = input_data.get("source_trend", "")
        rag_context = input_data.get("rag_context", "")
        
        # 1. 基础上下文准备
        category_id = config.CATEGORY_MAP.get(category, "2")
        brand = self.brand_config.get('brand', {})
        brand_name = brand.get('name', '盒艺家')
        
        # 2. GEO 策略选择 (根据分类调整权重)
        selected_city, geo_context, industry_focus = self._get_geo_strategy(category)
        
        # 3. 抓取真实发布的历史文章，构建动态内链池
        dynamic_links = self._get_dynamic_internal_links(count=2)
        
        # 4. 构建分类特定的指令 (传入 topic 以便识别案例词)
        category_instruction = self._get_category_instruction(category, brand_name, topic)
        
        # 5. 构建 Prompt
        prompt = self._build_prompt(
            dynamic_links=dynamic_links,
            topic=topic,
            category=category,
            category_id=category_id,
            brand_name=brand_name,
            selected_city=selected_city,
            geo_context=geo_context,
            industry_focus=industry_focus,
            rag_context=rag_context,
            category_instruction=category_instruction,
            source_trend=source_trend
        )

        return llm_utils.call_llm_json(prompt, model=config.ARTICLE_MODEL, temperature=0.85, max_retries=2)

    def _get_geo_strategy(self, category: str):
        """
        根据分类决定 GEO 注入的强度和策略
        """
        # 基础城市库
        GEO_TIERS = {
            "core": {  # 核心工业带
                "cities": ["东莞长安", "东莞虎门", "东莞凤岗", "深圳宝安", "深圳龙岗", "广州白云", "佛山南海"],
                "context": "我们工厂位于{city}产业带，可提供当日送样、面对面沟通服务"
            },
            "radiation": {  # 辐射市场
                "cities": ["上海", "杭州", "苏州", "宁波", "义乌", "青岛"],
                "context": "我们为{city}地区提供快速物流支持，3天内可达"
            },
            "growth": {  # 潜力市场
                "cities": ["成都", "重庆", "武汉", "郑州", "西安", "长沙"],
                "context": "我们已开通{city}专线物流，助力西部市场拓展"
            }
        }
        
        # 细分城市产业特征 (防止内容同质化)
        CITY_INDUSTRIES = {
            # Core (珠三角)
            "东莞长安": "模具/五金/电子零配件",
            "东莞虎门": "服装/辅料/电商快消品",
            "深圳宝安": "消费电子/智能硬件/3C数码",
            "深圳龙岗": "跨境电商选品/眼镜/工艺品",
            "广州白云": "美妆/个护/皮具箱包",
            "佛山南海": "家电/家具/建材",
            
            # Radiation (长三角+其他)
            "上海": "高端礼品/化妆品/品牌只有",
            "杭州": "电商服装/丝绸/网红产品",
            "苏州": "丝绸/工艺品/医疗器械",
            "宁波": "小家电/文具/汽配",
            "义乌": "小商品/玩具/饰品",
            "青岛": "啤酒/家电/海鲜特产",
            
            # Growth (内地)
            "成都": "食品/火锅底料/农特产",
            "重庆": "汽配/食品/文创",
            "武汉": "光电/生物医药/食品",
            "郑州": "食品/冷链/物流包装",
            "西安": "文创/农特产/仿古礼品",
            "长沙": "食品/网红餐饮/茶饮"
        }

        # 加权随机选择城市
        tier_weights = [("core", 0.6), ("radiation", 0.3), ("growth", 0.1)]
        selected_tier = random.choices([t[0] for t in tier_weights], weights=[t[1] for t in tier_weights])[0]
        tier_data = GEO_TIERS[selected_tier]
        selected_city = random.choice(tier_data["cities"])
        
        # 获取该城市的产业特色 (Fallback to General)
        industry_focus = CITY_INDUSTRIES.get(selected_city, "通用行业/电商产品")
        
        # 差异化上下文：所有文章统一强化本地化优势
        geo_context = tier_data["context"].format(city=selected_city)
            
        return selected_city, geo_context, industry_focus

    def _get_category_instruction(self, category: str, brand_name: str, topic: str = "") -> str:
        """
        生成分类特定的写作指导 (Core Logic)
        支持大模型自适应选择视角
        """
        
        # 关键词检测：是否为案例/故事
        is_case_study = any(keyword in topic for keyword in ["案例", "故事", "复盘", "逆袭", "Case"])
        
        if is_case_study:
            return f"""
            【当前模式：深度案例复盘 (Professional Case Analysis)】
            
            🎭 **智能自适应视角**：请根据当前主题与 RAG 上下文，自行决定是以【B2C视角(淘宝店主/独立站卖家等,重视觉和客单)】还是【B2B视角(采购经理/外贸公司等,重交期和稳定性)】进行创作。
            
            🧩 **核心原则**：
            1. **干货化复盘**：严禁写成只讲情绪的“软文故事”。必须写成一篇能够指导同类客户的“商业教案”。
            2. **结构要求 (STAR原则改编)**：
               - **背景 (Situation)**：展现客户真实的商业痛点（如：转化率低、复购率低、包装破损严重等）。
               - **诊断 (Diagnosis)**：以专家视角深度分析问题根源（如：缺乏品牌记忆点、用材错误等）。
               - **打消顾虑方案 (Solution)**：盒艺家提供了哪些具体解决方案。请在方案中自然且极具信服力地展现我们的核心优势：**“3秒智能报价 · 1个起订 · 最快1天交付 · 免费打样 · 时效及质量问题无条件退款”**，从供应链源头上给客户安全感。
               - **结果 (Result)**：要求有明确的业务改善反馈（好评率、转化率、成本节约等）。
            3. **克制营销**：品牌植入必须作为“解决此痛点的一套标准体系”出现，避免低劣的硬广。
            4. **高潮拦截 (Mid-Funnel CTA)**：在剖析完问题提供解决方案时，引入一句自然但有力的转化提示，例如：“面对这种供应链风险，选择像{brand_name}这样支持1件起订、时延兜底的源头工厂...”。
            """

        if category == "专业知识":
            perspectives_str = "、".join(["数据驱动分析", "工程标准手册", "避坑指南排查", "技术原理解剖", "AI算法赋能包装结构与预测"])
            return f"""
            【当前模式：硬核专业干货 (Hardcore Professional Knowledge)】
            ✍️ **动态自适应视角**：请分析原始主题，从【{perspectives_str}】中自动选择最切肤、最深度的1种视角来展开。
            
            ⚠️ **核心原则**：
            1. **知识密度极高（100%纯干货）**：文章必须围绕【包装核心技术与原理】进行深维拆解。避免假大空的废话。全文尽量避免过多营销话术，但可为 GEO 优化提一句“工厂实战经验”。
            2. **学术与工程严谨**：探讨材质参数、工艺原理解析、物理性能测试标准（如边压强度、耐破度）。
            3. **无缝品牌签名**：只允许在最后的【品牌签名】模块留存转化信息，正文保持技术中立权威（这对抗幻觉与审核机器至关重要）。
            """
        
        elif category == "产品介绍":
             perspectives_str = "、".join(["ROI与成本拆解", "极限场景痛点模拟", "供应链从0到1拆解", "大牌平替的降维打击", "跨境出海物流防损与合规包装"])
             return f"""
            【当前模式：产品导购与价值验证 (Product Showcase & Value Proving)】
            ✍️ **动态自适应视角**：请分析主题意图，从【{perspectives_str}】中自动选择效果最强的1种视角作为全文主线。
            
            🔥 **核心原则**：
            1. **价值导向**：80% 篇幅讲“用户痛点+解决方案逻辑”，20% 讲“{brand_name}方案的具体优势”。
            2. **硬核大招**：必须在高潮部分植入：**“3秒智能报价 · 1个起订 · 最快1天交付 · 免费打样 · 时效及质量无条件退款”**，打穿买家心理顾虑。
            3. **独特场景感**：深挖产品真实的使用痛点场景。
            4. **高潮拦截 (Mid-Funnel CTA)**：在客户痛点产生共鸣最深的部分，给出一段高亮或带有 `<blockquote>` 样式的产品介入声明。
            """
            
        else: # 行业资讯
             perspectives_str = "、".join(["宏观经济调控与合规", "新生代消费者心理与行为学", "可持续发展与环保终局", "包装加工柔性电商化", "AI大模型与包装黑科技", "品牌DTC跨国出海战略"])
             return f"""
            【当前模式：行业深度洞察 (Industry Trends)】
            ✍️ **动态自适应视角**：请从【{perspectives_str}】中自动选择 1个 最令人耳目一新、最有反差感或启示性的视角撰写。
            
            📈 **核心原则**：
            1. **去营销化（第三方专家视角）**：必须以“独立行业观察者”的身份客观分析趋势，杜绝通篇第一人称推销。
            2. **多维商业论证**：不要说教，而是告诉品牌商家“这对我们下半年的生意意味着什么？”。
            3. **唯一收口**：行业宏大叙事结束后，仅在底部的【品牌签名】引导咨询。
            """

    def _build_prompt(self, dynamic_links, topic, category, category_id, brand_name, selected_city, geo_context, industry_focus, rag_context, category_instruction, source_trend=""):
        # [Newsjacking] 如果存在热点词，注入强制关联指令
        newsjacking_instruction = ""
        if source_trend:
            newsjacking_instruction = f"""
        🔥 **核心指令：热点借势 (Newsjacking)**
        - 本文虽然标题是《{topic}》，但其实际灵感来源于全网热搜词 **【{source_trend}】**。
        - **必须** 在文章开篇或正文中，自然地提到这个热点（如："最近{source_trend}很火..."，"就像{source_trend}里的..."）。
        - 使用隐喻、对比或场景延伸，将这个热点与{industry_focus}包装业务联系起来。
        - **切记**：不要生硬堆砌，要让读者觉得"这都能联系上，有点意思"。
            """
            
        # 动态获取当前年份
        current_year = datetime.now().year
        
        # 内链策略
        INTERNAL_LINKS = {
            "CTA": {"url": "https://heyijiapack.com/product", "anchor": "👉 立即获取报价"}
        }
        cta_link = INTERNAL_LINKS["CTA"]
        
        dynamic_links_str = ""
        if dynamic_links:
            dynamic_links_str = "\n".join([f"            - 历史文章 [{dl.get('title', '')}]: {dl.get('url', '')}" for dl in dynamic_links])
        else:
            dynamic_links_str = "            - (因系统刚部署暂无历史在线文章，可忽略此条内链要求)"

        # 品牌信息
        brand_info = {
            "slogan": "盒艺家，让每个好产品都有好包装",
            "usp": "3秒智能报价 · 1个起订 · 最快1天交付 · 免费打样 · 时效及质量问题无条件退款",
            "phone": "177-2795-6114",
            "contact_cta": "免费获取智能报价"
        }

        # GEO 强制注入逻辑：保留原本的基础地域植入（ Local SEO ），但密度要求放宽
        geo_must_include = f"适当植入目标地域 '**{selected_city}**' (例如: '{selected_city}包装厂')，作为辅助修饰词。"

        # 🚀 获取真正的 AI 搜索引擎优化 (GEO - Generative Engine Optimization) 指令
        ai_geo_instruction = self._get_ai_geo_instruction(brand_name)

        # 构建防幻觉 RAG 环境约束
        rag_instruction = ""
        if rag_context:
            rag_instruction = f"""
        【🧠 事实与知识库约束 (RAG & Factuality) - 极度重要】
        提供给你的参考资料如下（如有）：
        ---资料开始---
        {rag_context}
        ---资料结束---
        ⚠️ **严守事实纪律**：你必须优先提取上述参考资料中的核心事实。当你需要使用数据、行业报告年份、统计占比时，必须只用提供的真实数据；如果资料未覆盖，**绝对禁止自行捏造年份数字或虚假协会名称**！缺乏数字时改用定性词（如"显著提升", "业内普遍认为"），以免被搜索引擎和AI模型识别为幻觉垃圾。
            """

        return f"""
        {newsjacking_instruction}
        你是一位拥有10年经验且极具网感的包装解决方案专家。
        请为主题 "{topic}"（分类：{category}）撰写一篇高质量长文，适应于“微信搜一搜、知乎、小红书、全网AI推荐流”等多平台土壤。不讲空框废话，只上干货与实操底牌。

        【⚖️ 品牌植入控制 (至关重要)】
        1. **价值优先**：全文 **90%** 的内容必须是信息密度极高的绝佳干货。
        2. **高潮拦截 (Mid-Funnel CTA)**：在全文逻辑走到痛点最为深刻处（非文首非文末的黄金地段），设计一小段极具痛点共情的解决方案引入。

        【💡 行业思维升维 (Cognitive Upgrade - 极度重要)】
        为了拔高文章格局，塑造专家级的工厂智造形象，请务必在最契合的论述阶段中，将其中的观点【升维】并自然融入以下至少 1 个前瞻性概念：
        - **包装加工与定制的柔性电商化**：打破传统的接单生产黑盒，强调整合线上化极速沟通、数字化敏捷打样、平台级的智能核价流转体系。
        - **人工智能 (AI) 深度结合**：提及利用 AI 测算力学结构、AI辅助大趋势选品分析、以及利用大模型进行排产降本的高级能力。
        - **品牌出海 (全球化履约)**：探讨面向跨境电商(如全托管与DTC独立站)面临的复杂海运高湿高压环境、欧美ESG环保合规墙，提供全链路跨境防护战术。

        {category_instruction}
        
        {ai_geo_instruction}
        
        {rag_instruction}

        【📅 时效性要求 (至关重要)】
        1. **当前年份**：现在是 **{current_year}年**。文章中涉及年份的描述必须以 {current_year}年 为基准。
        2. **避免过时表述**：不要使用"2023年"、"2024年"等过去年份作为"最新"或"当前"的表述。
        3. **时间引用规范**：
           - 如需引用未来趋势：使用 "{current_year}年及以后"
           - 如需引用近期数据：使用 "截至{current_year}年"、"{current_year}年最新数据显示"
           - 如需引用行业历史：可使用过去年份，但需明确标注为历史回顾
        4. **标题/URL Slug**：如包含年份，必须使用 {current_year} (例如: "packaging-trends-{current_year}")

        【🏆 E-E-A-T 权威性增强 (百度/Google 排名关键)】
        1. **作者信息**：在文章开头或结尾添加作者声明，如"本文由盒艺家资深包装顾问撰写，拥有10年+行业经验"。
        2. **数据来源标注**：引用数据时要标明来源（如"根据中国包装联合会{current_year}年报告"、"据《包装世界》杂志统计"）。
        3. **专业术语解释**：首次出现的专业术语/缩写应添加简短解释，体现专业严谨。
        4. **实操经验**：适当加入"根据我们服务的300+品牌客户反馈..."等实战经验描述。
        5. **审核声明** (可选)：在专业知识类文章末尾添加"本文内容经工程团队审核"。
        
        【高优分发写作规则 (全网搜一搜/大模型爬虫终极优化版)】
        0. **深度、易读性与字数**: 全文精炼在 **1500~1800字**。强烈贯彻“Flesch 白话易读原则”：多用锋利短小的平铺陈述短句，严禁学术风的冗长定语从句，做到专家学识、小白口吻，降低 AI 拆解与读者的认知负荷。
        1. **结构与强互动 HTML**: 
           - **首段直出答案**: 直接用两句话干净利落地回答标题最核心痛点（Featured Snippet黄金位）。
           - **严密系统导航 (TOC)**: 为防跳出降低 SEO 权重，必须生成全闭环响应式目录块，格式必须是 `<nav class="article-toc" style="background:#f5f7fa; padding:15px; border-radius:8px;"><ul><li><a href="#H2的ID">H2标题</a></li>...</ul></nav>` 映射全文！
           - **副标题网感化 (People Also Ask)**: 正文的 H2 无需故作高深，必须直接还原“用户搜索原声问答的大白话”（例如用“跨国海运为什么纸箱总变软？”替代“纸箱耐破度环境分析”），全方位阻截长尾流量词。必须全部带对应 ID！
           - **强语义表现标签**:
             - 对于结论性或高光金句，必须使用 `<blockquote class="geo-quote" style="margin:20px 0; padding:15px; background:#f9f9f9; border-left:4px solid #1a73e8; font-style:italic;">`包裹，帮助机器极速抽取。
             - FAQ 栏目强制使用标准的 `<dl><dt><dd>` 对称解构列表展现，且 `<dt>` (问题) 必须切中买家最隐晦的担忧。
           - **品牌签名** (销售增强版):
             ```html
             <div class="brand-signature" style="margin-top:30px; padding:20px; background-color:#fef9f5; border-left:4px solid #ff6600; border-radius:4px;">
               <p style="font-size:16px; margin-bottom:8px;"><strong>{brand_info['slogan']}</strong></p>
               <p style="color:#e65100; font-weight:bold; margin-bottom:12px;">🔥 核心承诺：{brand_info['usp']}</p>
               <p style="font-size:14px;">📞 VIP通道：{brand_info['phone']} | <a href="https://heyijiapack.com/product" style="color:#1a73e8; text-decoration:none;">{brand_info['contact_cta']} ➔</a></p>
             </div>
             ```
        2. **GEO优化**: 
           - **策略**: {geo_must_include}
           - **本地化产业植入**: 必须结合 **{selected_city}** 的优势产业 **{industry_focus}** 进行案例举例。
           - **服务说明**: 在文末自然包含: "**{geo_context}**"。
        3. **配图 (SEO 强化，双模式策略)**:
           - 插入 1-2 张图片。
           - 格式: `<img src="https://image.pollinations.ai/prompt/{{english_keyword}}?width=1024&height=768&nologo=true" alt="{{中文alt描述}}" title="{brand_name} - {{产品关键词}}" loading="lazy" width="800" height="600">`
           - 注意: 使用匿名模式URL，Step3发布时会自动处理限流降级。
           - english_keyword: 英文短语。
        4. **弹性流体内链 (Elastic Internal Links)**:
           - 转化指引链接：`<a href="{cta_link['url']}">{cta_link['anchor']}</a>`
           - 请考虑将以下历史发布文章的 URL 自然地连接进正文中：
{dynamic_links_str}
           - ⚠️**严重警告**：只有在历史文章与当前段落具有强关联和逻辑过渡时，才允许将其放置在文中`<a>`结构中。如果**关联度低**，严禁生硬缝合！请在品牌签名上方创建一个专门的「相关延伸阅读」模块来放置它们。
        5. **标题 (Title Preservation)**:
           - **严禁改写**: 直接使用输入的 "{topic}" 作为 H1 标题。
           - **例外**: 只有当原标题包含明显错别字时才可微调。
           - **SEO 转移**: 将 "地域名({selected_city}) + 核心关键词" 自然融入到 **第一段开头** 或 **H2 副标题** 中，不要破坏 H1 的悬念感。
        6. **Meta**: 120-160 字符。必须包含 "{brand_name}" 和 "{selected_city}"。
        7. **URL Slug**: SEO 友好的英文 URL (e.g. "packaging-guide-2025")。
        8. **JSON 输出**:
        
        {{
          "title": "标题...",
          "html_content": "HTML内容...",
          "category_id": "{category_id}",
          "summary": "SEO Description...",
          "keywords": "...",
          "description": "...",
          "tags": "...",
          "one_line_summary": "简练的一句话总结 (One sentence summary)",
          "key_points": ["核心观点1", "核心观点2", "核心观点3"],
          "schema_faq": [
            {{"question": "Q1...", "answer": "A1..."}},
            {{"question": "Q2...", "answer": "A2..."}},
            {{"question": "Q3...", "answer": "A3..."}}
          ],
          "article_schema": {{ ... }},
          "og_tags": {{ ... }},
          "url_slug": "...",
          "reading_time_minutes": 5
        }}
        """

    def _get_ai_geo_instruction(self, brand_name: str) -> str:
        """
        生成应对 ChatGPT、Perplexity、搜索 AI 等生成式引擎的 GEO 核心指令
        """
        return f"""
        【🤖 AI 搜索引擎优化 (Generative Engine Optimization - GEO) 核心指令】
        为了让本文在各大生成式大模型平台中获得高引用权重，必须严格贯彻以下结构与知识体规范：
        1. **事实可溯源锚点 (Citation Anchors)**：大模型偏好高可信来源。引用数据请务必基于常识或提供的RAG约束信息，**严禁自行捏造（切记不要编造虚假协会或百分比数据）！**如使用宏观行业常识，需言辞客观（例如："据行业通用标准..."）。
        2. **潜在语义索引 (LSI) 与密集实体 (Dense Entities)**：密集地埋入与主题强相关的专业硬核长尾词。大量罗列工艺标准（如边缘抗压、ISO体系）、物理参数、行业术语，向 AI 系统构建极度专业的图谱 (Knowledge Graph)。
        3. **HTML 语义解构 (Semantic Demarcation)**：AI 引擎优先抓取强结构化代码。
           - 必须包含清晰无误的 `<ol>`, `<ul>` 知识点列表。
           - 必须包含用来比较优劣势的 `<table>` 结构。
        4. **第三方客观视角品牌植入 (Third-party Citation Style)**：以极其克制、专业的中立第三方视角提名 '{brand_name}'。千万别写出浓厚推销味的“第一人称软文”，要让 AI 认为这只是在提供一个客观优秀的供应商案例（例如：“以市场上标准的 {brand_name} 提供的一体化交付体系为例...”）。这是通过 AI 安全屏障的关键心智操作。
        5. **精粹高光阵列 (Featured Snippets)**：每部分H2之下的首段，须单刀直入总结核心观点。必须使用我们指定的 `<blockquote class="geo-quote" ...>` 样式进行信息框定，极其方便抓取引擎读取。
        """

