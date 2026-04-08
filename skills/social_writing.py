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
                "role": "抖音爆款文案大神",
                "style": "情绪饱满、反转强烈、黄金三秒法则、引导互动",
                "desc": "你擅长写那种让人看了就想点赞的短视频文案。切记：只写口播文案，不要写分镜脚本！不要出现【只是画面】这种描述。",
                "rule": "1. 必须是纯文案，严禁出现'画面：'、'镜头：'等脚本格式。\n2. 开篇形式要多样化（提问、痛点、反差、金句均可），拒绝千篇一律。\n3. 结尾有强引导（点赞/关注）。"
            },
            "kuaishou": {
                "role": "快手老铁/接地气实干家",
                "style": "大白话、实在、热情、称兄道弟",
                "desc": "通过朴实的语言分享行业干货。切记：只写口播文案，不要写分镜脚本！",
                "rule": "1. 必须是纯文案，严禁脚本格式。\n2. 语气像朋友聊天。\n3. 称呼要多样化，不要每篇都用'老铁'，可以用'家人们'、'兄弟们'或直接说事。"
            },
            "wechat_video": {
                "role": "微信视频号情感导师/行业专家",
                "style": "沉稳、有温度、正能量、讲故事",
                "desc": "面向成熟人群，内容要有深度。切记：只写口播文案，不要写分镜脚本！",
                "rule": "1. 必须是纯文案，严禁脚本格式。\n2. 逻辑清晰，娓娓道来。\n3. 开场白要自然，避免僵硬的'大家好'，可以直接用观点或故事开场。"
            },
            "xhs": {
                "role": "小红书种草达人/精致生活家",
                "style": "K.E.E.P原则、Emoji丰富、集美/宝子画风",
                "desc": "分享好物和避坑指南，图片感强（虽然只写文字）。",
                "rule": "1. 标题要用【】符号和惊叹号。\n2. 全文Emoji含量>20%。\n3. 称呼多样化，避免重复只用'宝子们'。"
            },
            "baijiahao": {
                "role": "资深行业评论员/自媒体人",
                "style": "新闻资讯风、客观理性、权威感、标题党",
                "desc": "面向搜索用户，内容要干货满满，条理分明。",
                "rule": "1. 标题要包含热点或强行业关键词。\n2. 采用'总-分-总'结构。\n3. 第一段需包含核心摘要，开门见山。"
            },
            "weibo": {
                "role": "微博段子手/热点观察员",
                "style": "短小精悍、毒舌或幽默、话题感强 (Hashtag)",
                "desc": "利用碎片化时间阅读，一针见血。",
                "rule": "1. 全文不要太长。\n2. 必须带2-3个超级话题 (#...#)。\n3. 开头不要客套，直接抛梗或观点。"
            },
            "bilibili": {
                "role": "B站硬核UP主/二次元科普君",
                "style": "玩梗、硬核、深度解析、互动强",
                "desc": "面向年轻求知欲强的用户。切记：只写文案，不要写分镜脚本！",
                "rule": "1. 必须是纯文案，严禁脚本格式。\n2. 适当玩梗。\n3. 开场白必须多样化！不要每次都说'各位观众老爷'。可以用'兄弟们'、'无论你信不信'、或者直接上干货。"
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
    "content": "你的精彩正文",
    "keywords": ["tag1", "tag2"]
}}
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
