import sys
import os
import json
import re
import random
from typing import Dict, Any

from core.skill import BaseSkill
from shared import config, llm_utils

class SocialWriterSkill(BaseSkill):
    """
    技能: 全平台社交媒体文案创作 (矩阵版)
    集成 7 种不同的创作人格，针对不同平台输出定制化风格的文章。
    """
    def __init__(self):
        super().__init__(
            name="social_writing",
            description="根据平台特性，将长文章重写为适应不同社交媒体的内容"
        )
        self._init_prompts()

    def _init_prompts(self):
        """初始化各平台的专属人设和指令"""
        self.PROMPTS = {
            "douyin": {
                "role": "深耕产业一线的源头硬核厂长/供应链操盘手",
                "style": "底层揭秘、降维打击、极高信息密度",
                "desc": "以顶级源头厂长的视角，把高大上的包装技术拆解成极具反差的大白话。切记只有文字口播！",
                "rule": "1. 严禁出现'画面：'等脚本格式。\n2. **【终极客群锁定】：你的受众是【受众1-微创客与淘宝/DTC出海卖家】。**\n3. 你必须在文案高潮处，痛批行业“起订量高、打样慢、出海易破损”的现状，最后引出我们的杀手锏：**【1个起订、免费极速打样、出海防潮合规箱】** 来兜底救场！"
            },
            "kuaishou": {
                "role": "实战派包装厂大掌柜/接地气生意人",
                "style": "大白话算账、实在粗犷、讲红利",
                "desc": "以做生意的视角，给客户兄弟算成本账、效率账。切记：只写纯口播文案！",
                "rule": "1. 严禁脚本格式，像老炮开会。\n2. **【终极客群锁定】：你的受众是【受众1-小微商家与带货主播】。**\n3. 必须在讲痛点时暴露出咱们的下沉红利杀手锏（**支持1件起订试错、烂了全赔**等）。"
            },
            "wechat_video": {
                "role": "资深智能制造商业教头/大厂内参",
                "style": "沉稳降维、痛点拆解、大局观视角",
                "desc": "面向成熟企业主或大厂采购总监，讲究商业逻辑与交付履约。切记口播文案！",
                "rule": "1. 拒用低级鸡汤，全篇干货拆解。\n2. **【终极客群锁定】：你的受众是【受众2-实体大厂采购与供应链高管】。**\n3. 绝对不要谈花里胡哨的设计！痛点聚焦“交期延误、报价虚高卡进度”。抛出我们的超级底牌：**【3秒在线智能报价、1天光速交付、质量延误满额兜底】** 以解除其背锅风险。"
            },
            "xhs": {
                "role": "见多识广的包装界避坑指南/视觉设计情报官",
                "style": "成分党干货分析、排雷避坑、颜值即正义、带网感",
                "desc": "转为【材质/高颜值极客】。分享避坑指南与硬核干货图文配文。",
                "rule": "1. 标题采用【】加反常识冲击。\n2. **【终极客群锁定】：你的受众是【受众3-品牌设计主理人与高端礼品企划】。**\n3. 核心大招环节，一定要抨击传统工厂审美拉胯、软塌塌，抛出 **【AI包装结构设计+高阶材质精细打样】** 提升30%溢价的降维大牌！"
            },
            "baijiahao": {
                "role": "资深产业数字观察员/供应链研究院士",
                "style": "新闻资讯风、数据客观、权威感、产业升维",
                "desc": "面向搜索用户与同行企业主，内容充斥信息差和行业终局视角。",
                "rule": "1. 标题要带强行业趋势属性，采用总分总结构。\n2. **【终极客群锁定】：你的受众是【受众2-实体B2B企业老板与采购】。**\n3. 强关联“中国供应链数字化大势”，并且把我们的 **【3秒秒报价、极速交付体系】** 拔高为行业标杆案例展示。"
            },
            "weibo": {
                "role": "包装圈一线吃瓜情报员/硬核毒舌",
                "style": "短小锋利、一针见血、热点嫁接",
                "desc": "短阅读，对行业乱象毫不留情地开炮。",
                "rule": "1. 全文精炼，直击痛点。\n2. **【受众偏好：普适微商与独立站】**。\n3. 直接抛观点，结尾狠狠引流到 **1件起订+免费打样** 上。"
            },
            "bilibili": {
                "role": "B站极客包装评测官/供应链硬核解密UP主",
                "style": "技术流分析、拆解测评、无情打假、玩梗",
                "desc": "面向求知欲极强的硬核商户受众或产品经理。",
                "rule": "1. 严禁分镜脚本。\n2. **【终极客群锁定】：【受众3-产品经理/硬核极客卖家】**\n3. 高潮处一定要亮出 **【AI大模型辅助包装结构算力测算】** 的黑科技威望，不只讲打样，更要讲算法降本！"
            }
        }

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Input: source_title, source_content, platform_config
        """
        s_title = input_data.get("source_title", "")
        s_content = input_data.get("source_content", "")
        p_conf = input_data.get("platform_config", {})
        
        # 识别平台 Key (config 中 key 应与 prompts key 对应)
        # 我们在 config.py 中定义的 key 就是 douyin, xhs 等
        # 但 runner 传过来的是 p_conf 字典，我们需要反推 key 或者让 runner 传 key
        # 修正: Agent runner 并没有把 key 塞进 platform_config，agent_runner 传了 key 给 agent, agent传了 p_conf
        # 我们需要在 Agent 中把 'key' 也塞进去，或者通过 p_conf['name'] 模糊匹配
        # 最稳妥：在 agent.py 里把 key 塞入 p_conf 或 input_data
        
        # 暂时用 name 模糊匹配，或者增加一个 mapping
        p_name = p_conf.get("name", "")
        p_key = "xhs" # default
        
        if "抖音" in p_name: p_key = "douyin"
        elif "快手" in p_name: p_key = "kuaishou"
        elif "微信" in p_name: p_key = "wechat_video"
        elif "小红书" in p_name: p_key = "xhs"
        elif "百家" in p_name: p_key = "baijiahao"
        elif "微博" in p_name: p_key = "weibo"
        elif "B" in p_name or "bili" in p_name.lower(): p_key = "bilibili"
        
        prompt_setting = self.PROMPTS.get(p_key, self.PROMPTS["xhs"])
        
        limit_title = p_conf.get("title_limit", 20)
        limit_content = p_conf.get("content_limit", 900)
        limit_kw = p_conf.get("keywords_limit", 4)
        
        print(f"      ✍️ [Skill] 激活人设: 【{prompt_setting['role']}】 -> 创作 {p_name} 内容...")
        
        # [Feature] 强制随机开场策略，解决 "兄弟们" 重复问题
        OPENING_STYLES = [
            "【提问开场】：用一个扎心的反问句开头，直击痛点。禁止使用'大家好'。",
            "【数据开场】：直接抛出一个惊人的行业数据或对比结论。禁止使用'兄弟们'。",
            "【故事开场】：用'我有个朋友...'或'昨天遇到个客户...'这种真实场景开头。",
            "【观点开场】：开门见山抛出违反常识的暴论或独家观点。",
            "【场景开场】：描述一个具体的焦虑场景，让用户对号入座。",
            "【悬念开场】：'你绝对想不到...'，设置巨大悬念。",
            "【避坑开场】：'千万别再...'，直接警告用户。",
            "【金句开场】：引用或创造一句行业金句。"
        ]
        selected_opening = random.choice(OPENING_STYLES)
        
        # 1. 构造 System Prompt (预留缓冲: 告诉AI目标比实际限制少2字)
        effective_title_limit = limit_title - 2  # 18 -> 16
        system_prompt = f"""你现在的身份是：{prompt_setting['role']}。
你的写作风格是：{prompt_setting['style']}。
任务描述：{prompt_setting['desc']}

【核心规则】
{prompt_setting['rule']}
4. 【去硬广化原则】正文内容中务必以客观/达人中立视角输出，严禁生硬地推销'盒艺家'，即使引用也应以极为自然克制的行业标杆提及，重点在于提供情绪价值或专业分析。
5. 【硬性要求】标题必须控制在 {effective_title_limit} 字以内，绝对不能超过！这是最重要的规则。
6. 正文严格控制在 {limit_content} 字以内（可少不可多）。
7. 提取 {limit_kw} 个关键词。
8. 输出仅限纯文本，严禁包含任何图片URLs、[图片]占位符或Markdown图片语法 ![](...)。

【强制开场指令】
本次写作必须使用 {selected_opening}
严禁使用'兄弟们'、'家人们'、'大家好'、'各位观众老爷'等陈词滥调作为第一个词！
"""

        # 2. 构造 User Prompt (含 Few-shot 示例)
        user_prompt = f"""
请将这篇枯燥的文章重写为一篇精彩的【{p_name}】爆款内容：

【原文标题】：{s_title}
【原文片段】：
{s_content[:2000]}...

【标题示例】（注意：标题必须≤{effective_title_limit}字，以下是合格示例）：
✅ "包装设计三大误区" (7字)
✅ "纸盒选材避坑指南" (7字)  
✅ "环保包装正确打开方式" (9字)
✅ "这款礼盒月销百万的秘密" (11字)

【输出格式】(JSON):
{{
    "title": "你的神标题（≤{effective_title_limit}字）",
    "content": "你的精彩正文（务必在段落终点生成 3~5 个能够精准圈定同城/产业客群的 Hashtag 超级话题，例：#出海包装 #AI智造 #源头工厂）",
    "keywords": ["tag1", "tag2"]
}}

⚠️【架构存活警告 (JSON Safety)】：你输出的 JSON 非常重要。不要有多余的推导废话。在 `content` 字段的字符串内部绝对不允许出现未经转义的换行符（回车必须写作 `\\n`），如果你要在内容中使用双引号请改用单引号！否则序列化将发生特大故障。
"""

        try:
            resp = llm_utils.call_llm_with_retry(
                prompt=user_prompt,
                system_prompt=system_prompt,
                model=config.LLM_MODEL,
                temperature=0.85 # 稍微高一点增加创意
            )
            
            # 4. 解析
            content_str = resp.strip()
            start = content_str.find("{")
            end = content_str.rfind("}")
            if start != -1 and end != -1:
                json_str = content_str[start:end+1]
                
                # [Fix] JSON Cleaning for robustness
                # 1. Remove invalid control characters (0x00-0x1f) except \n, \r, \t
                json_str = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', json_str)
                
                # 2. Use strict=False to allow control chars inside strings (e.g. unescaped newlines)
                try:
                    data = json.loads(json_str, strict=False)
                    return data
                except json.JSONDecodeError:
                    # Retry: sometimes AI puts newlines that break JSON. try to escape key newline chars?
                    # Simplified fallback: simply try without strict=False (unlikely to help if strict=False failed)
                    # Let's try to grab just keywords if title/content is broken?
                    # For now, just let it fail to the outer except block which prints the error
                    raise
            else:
                # Fallback extraction if JSON fails
                return {
                    "title": f"🔥 {s_title[:15]}",
                    "content": resp, # Return raw text as content
                    "keywords": []
                }
                
        except Exception as e:
            print(f"      ❌ 生成异常: {e}")
            return None
