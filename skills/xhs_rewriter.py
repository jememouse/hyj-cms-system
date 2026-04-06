import sys
import os
import json
from typing import Dict
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.skill import BaseSkill
from shared import config, llm_utils

class XHSRewriterSkill(BaseSkill):
    """
    技能: 将长文章重写为小红书笔记 (K.E.E.P 模式)
    """
    def __init__(self):
        super().__init__(
            name="xhs_rewrite", 
            description="使用 K.E.E.P 公式将文章重写为小红书风格"
        )
        
        # Prompt 保持不变
        self.SYSTEM_PROMPT = """你是一个在包装行业深耕10年的资深采购经理，人设是“犀利、懂行、爱分享”。
你的目标是将枯燥的行业知识，转化为小红书平台爆火的“种草/避坑”笔记。

请遵循 [K.E.E.P] 创作公式：
1. K (Keywords): 标题必须包含痛点关键词（如“被坑哭”、“血泪教训”、“老板必看”）。
2. E (Emoji): 全文 Emoji 含量 > 15%，每段开头必须用 Emoji 下沉。
3. E (Emotion): 情绪价值拉满，不要讲课，要像闺蜜一样吐槽或安利。
4. P (Call to Action): 结尾引导评论或私信。

语言风格：
- 拒绝爹味，拒绝教科书式的废话。
- 多用短句，多用感叹号！
- 加上 #标签。
"""

    def execute(self, input_data: Dict) -> Dict:
        """
        Input: {"title": str, "content": str}
        Output: {"title": str, "content": str, "keywords": str}
        """
        title = input_data.get("title")
        content = input_data.get("content")
        
        # 截取上下文
        context = content[:2000] + "..." if len(content) > 2000 else content

        prompt = f"""
请将以下长文章改写为一篇小红书笔记。

【原始文章标题】: {title}
【原始文章内容】: 
{context}

---
【要求】
1. 输出格式必须是 JSON，包含 'title' 和 'content' 和 'keywords' 三个字段。
2. 'title': 20字以内，极其吸睛。
3. 'content': 900字以内，分段清晰。
4. 'keywords': 提取 5 个适合做标签的关键词 (e.g. "包装设计", "创业搞钱")。
"""
        result = llm_utils.call_llm_json(
            prompt=prompt,
            system_prompt=self.SYSTEM_PROMPT,
            temperature=1.3,
            max_retries=2
        )
        
        if result:
            return result
        else:
            print("   ⚠️ LLM/JSON 解析失败，返回 Fallback 数据")
            return {
                "title": f"🔥 {title}",
                "content": context,
                "keywords": "包装定制, 避坑指南"
            }
