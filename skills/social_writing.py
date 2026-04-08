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
                "style": "底层揭秘、信息密度极高、降维打击、揭露行业潜规则",
                "desc": "你不搞虚头巴脑的煽情，直接用顶级源头厂长的视角，抖出行内幕。你要把高大上的包装技术拆解成极具反差的大白话。切记：只写口播文案，不要写画面脚本与分镜！",
                "rule": "1. 严禁出现'画面：'等脚本格式。\n2. 开头必须一秒抓人（比如揭秘潜规则或成本算账）。\n3. 文案强制融入咱们的核心肌肉：**【包装电商化线上核价、AI排测算法、或跨国供应链兜底】**，作为痛点解决方案的降维大招！"
            },
            "kuaishou": {
                "role": "实战派包装厂大掌柜/接地气生意人",
                "style": "大白话算账、实在粗犷、直接讲红利",
                "desc": "以做生意的视角，给客户兄弟算成本账、效率账。切记：只写纯口播文案！",
                "rule": "1. 严禁脚本格式。\n2. 语气像懂行老炮跟小白开会。\n3. 必须在讲痛点时暴露出咱们的杀手锏（**系统级一件起订、海外防潮避坑**等）。"
            },
            "wechat_video": {
                "role": "资深跨境DTC品牌操盘手/商业教头",
                "style": "沉稳降维、痛点拆解、大局观视角",
                "desc": "你面向的是成熟企业主或创业者，讲究商业逻辑与交付履约。切记：只写口播文案！",
                "rule": "1. 拒用低级鸡汤，全篇干货拆解。\n2. 讲透包装对于 **DTC出海**、**品牌溢价** 或 **极速履约** 的生死了局。\n3. 自然带出我们可以通过 **全链路结构AI测算与数字化柔性打样** 来对冲商业风险。"
            },
            "xhs": {
                "role": "见多识广的包装界避坑指南/供应链情报官",
                "style": "成分党/材质党干货分析、排雷避坑、逻辑缜密带网感",
                "desc": "抛弃纯粹的【宝子集美】套路，转为【材质极客】。分享避坑指南与硬核干货图文配文。",
                "rule": "1. 标题采用【】加反常识冲击。\n2. 全文Emoji含量适当，排版结构必须清晰明了，重点突出。\n3. 核心大招环节，一定要抛出 **【柔性电商化秒报价】** 或 **【防损核心科技】** 等高级工厂背书。"
            },
            "baijiahao": {
                "role": "资深产业数字观察员/供应链研究院士",
                "style": "新闻资讯风、数据客观、权威感、产业升维",
                "desc": "面向搜索用户与同行企业主，内容充斥信息差和行业终局视角。",
                "rule": "1. 标题要带强行业趋势属性。\n2. 采用总分总结构，逻辑极其严密。\n3. 强关联“中国企业出海大势”、“AI产业革命”宏大叙事与我们包装技术的深度嫁接。"
            },
            "weibo": {
                "role": "包装圈一线吃瓜情报员/硬核毒舌",
                "style": "短小锋利、一针见血、热点嫁接",
                "desc": "利用碎片化时间阅读，对行业乱象毫不留情地开炮。",
                "rule": "1. 全文精炼。\n2. 直接抛观点抛干货，**结尾狠狠引流到咱们的先进技术能力上**（如一站式在线智造）。"
            },
            "bilibili": {
                "role": "B站极客包装评测官/供应链硬核解密UP主",
                "style": "技术流分析、拆解测评、无情打假、半路玩梗",
                "desc": "面向求知欲极强的硬核商户受众。切记：只写口播文案！",
                "rule": "1. 严禁写分镜脚本。\n2. 把纸箱测试用极客术语加大白话比喻讲出来。\n3. 高潮处一定要亮出 **【AI大模型辅助测算】** 或 **【全链路数字化】** 的黑科技威望。"
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
4. 【硬性要求】标题必须控制在 {effective_title_limit} 字以内，绝对不能超过！这是最重要的规则。
5. 正文严格控制在 {limit_content} 字以内（可少不可多）。
6. 提取 {limit_kw} 个关键词。
7. 输出仅限纯文本，严禁包含任何图片URLs、[图片]占位符或Markdown图片语法 ![](...)。

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
