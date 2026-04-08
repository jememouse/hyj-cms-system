"""
统一的 LLM 工具类
提供 JSON 解析、清洗和健壮性处理
"""
import json
import re
import time
import requests
from typing import Optional, Dict, Any
from shared import config


def extract_json(content: str) -> Optional[Dict]:
    """
    从 LLM 响应中提取 JSON (支持多种格式)

    使用三重解析策略:
    1. 直接解析整个内容
    2. 正则匹配最外层 JSON 对象
    3. 括号深度追踪找出完整 JSON

    Args:
        content: LLM 响应文本

    Returns:
        解析后的字典，如果失败返回 None
    """
    if not content:
        return None

    # 清洗内容
    content = sanitize_json(content)

    # 方法1: 直接解析
    try:
        return json.loads(content, strict=False)
    except json.JSONDecodeError:
        pass

    # 方法2: 正则匹配最外层 JSON 对象
    json_match = re.search(r'\{[\s\S]*\}', content)
    if json_match:
        try:
            return json.loads(json_match.group(), strict=False)
        except json.JSONDecodeError:
            pass

    # 方法3: 括号深度追踪
    depth, start_idx = 0, -1
    for i, char in enumerate(content):
        if char == '{':
            if depth == 0:
                start_idx = i
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0 and start_idx != -1:
                try:
                    json_str = content[start_idx:i+1]
                    return json.loads(json_str, strict=False)
                except json.JSONDecodeError:
                    start_idx = -1

    return None


def sanitize_json(text: str) -> str:
    """
    修复 LLM 生成的非法转义字符

    常见问题:
    - 非法反斜杠 (如 "10\20" 应该是 "10\\20")
    - 控制字符 (0x00-0x1f)

    Args:
        text: 待清洗的文本

    Returns:
        清洗后的文本
    """
    # 1. 修复非法转义 (保留合法的 \\ \" \/ \b \f \n \r \t \u)
    text = re.sub(r'\\(?![\\"/bfnrtu])', r'\\\\', text)

    # 2. 移除非法控制字符 (但保留换行符和制表符)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)

    return text


def extract_json_array(content: str) -> Optional[list]:
    """
    从 LLM 响应中提取 JSON 数组

    Args:
        content: LLM 响应文本

    Returns:
        解析后的列表，如果失败返回 None
    """
    if not content:
        return None

    content = sanitize_json(content)

    # 方法1: 直接解析
    try:
        result = json.loads(content, strict=False)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # 方法2: 正则匹配数组
    array_match = re.search(r'\[[\s\S]*\]', content)
    if array_match:
        try:
            result = json.loads(array_match.group(), strict=False)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    return None


def call_llm_with_retry(
    prompt: str,
    system_prompt: str = None,
    model: str = None,
    temperature: float = 1.0,
    max_retries: int = 2,
    retry_delay: float = 1.0
) -> str:
    """
    带重试 + 自动回退的 LLM 调用

    调用策略:
      1. 主通道 (DeepSeek 官方) 重试 max_retries 次
      2. 若主通道全部失败且配置了备用 Key，切换到备用通道 (OpenRouter) 再重试一轮

    Args:
        prompt: 用户提示词
        system_prompt: 系统提示词
        model: 模型名称 (默认使用 config.LLM_MODEL)
        temperature: 温度参数
        max_retries: 每个通道的最大重试次数
        retry_delay: 重试延迟（秒）

    Returns:
        LLM 响应内容
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    def _build_headers(api_key: str, api_url: str) -> dict:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        if "deepseek" in api_url or "openrouter" in api_url:
            headers["HTTP-Referer"] = "https://github.com/jememouse/deepseek-feisu-cms"
            headers["X-Title"] = "DeepSeek CMS Agent"
        return headers

    def _try_channel(api_key: str, api_url: str, api_model: str, channel_name: str) -> Optional[str]:
        """尝试在单个通道上完成请求，成功返回内容，失败返回 None"""
        headers = _build_headers(api_key, api_url)
        payload = {
            "model": api_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 8192
        }

        for attempt in range(max_retries + 1):
            try:
                resp = requests.post(api_url, headers=headers, json=payload, timeout=90)

                if resp.status_code == 200:
                    data = resp.json()
                    if 'choices' in data:
                        print(f"   ✨ [{channel_name}] 调用成功")
                        return data['choices'][0]['message']['content']
                    else:
                        print(f"   ⚠️ [{channel_name}] 响应格式异常: {data}")
                else:
                    print(f"   ⚠️ [{channel_name}] 错误 [{resp.status_code}]: {resp.text[:200]}")

            except requests.exceptions.Timeout:
                print(f"   ⚠️ [{channel_name}] 请求超时 (尝试 {attempt + 1}/{max_retries + 1})")

            except Exception as e:
                print(f"   ❌ [{channel_name}] 请求异常: {e}")

            if attempt < max_retries:
                time.sleep(retry_delay * (attempt + 1))

        return None  # 该通道所有重试均失败

    # ── 免费前置通道: Google GenAI 模型 ──
    # 判断是否被指令强制解耦到其他模型平台
    force_skip_google = False
    if model and ("gemma" not in model.lower() and "gemini" not in model.lower()) and model != getattr(config, 'GOOGLE_GENAI_MODEL', ''):
        force_skip_google = True

    if not force_skip_google and hasattr(config, 'GOOGLE_GENAI_API_KEY') and config.GOOGLE_GENAI_API_KEY:
        use_google_model = model if model and ("gemma" in model.lower() or "gemini" in model.lower()) else config.GOOGLE_GENAI_MODEL
        print(f"   🆓 尝试使用 Google GenAI 前置通道 ({use_google_model})...")
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=config.GOOGLE_GENAI_API_KEY)
            
            prompt_text = ""
            if system_prompt:
                prompt_text += f"{system_prompt}\n\n"
            prompt_text += prompt

            for attempt in range(max_retries + 1):
                try:
                    response = client.models.generate_content(
                        model=use_google_model,
                        contents=prompt_text,
                        config=types.GenerateContentConfig(
                            temperature=temperature,
                            max_output_tokens=8192
                        )
                    )
                    if response and response.text:
                        print(f"   ✨ [Google GenAI] 调用成功")
                        return response.text
                    else:
                        print(f"   ⚠️ [Google GenAI] 响应为空")
                except Exception as e:
                    print(f"   ❌ [Google GenAI] 请求异常 (尝试 {attempt + 1}/{max_retries + 1}): {e}")
                
                if attempt < max_retries:
                    time.sleep(retry_delay * (attempt + 1))
        except ImportError:
            print("   ⚠️ [Google GenAI] 未检测到 google-genai 库，请先执行 `pip install google-genai`。")
        except Exception as e:
            print(f"   ⚠️ [Google GenAI] 客户端初始化异常: {e}")
            
        print("   ⚠️ 免费前置通道失败，即将降级到原有主通道策略...")

    # ── 主通道: DeepSeek 官方 ──
    primary_model = model or config.LLM_MODEL
    result = _try_channel(config.LLM_API_KEY, config.LLM_API_URL, primary_model, "DeepSeek官方")
    if result:
        return result

    # ── 备用通道: OpenRouter 兜底 ──
    if config.FALLBACK_API_KEY:
        print("   🔄 主通道失败，切换到 OpenRouter 备用通道...")
        fallback_model = config.FALLBACK_MODEL
        result = _try_channel(config.FALLBACK_API_KEY, config.FALLBACK_API_URL, fallback_model, "OpenRouter备用")
        if result:
            return result

    print("   ❌ 所有通道均已失败")
    return ""


def call_llm_json(
    prompt: str,
    system_prompt: str = None,
    model: str = None,
    temperature: float = 1.0,
    max_retries: int = 2
) -> Optional[Dict]:
    """
    调用 LLM 并自动解析 JSON 响应

    Args:
        prompt: 用户提示词
        system_prompt: 系统提示词
        model: 模型名称
        temperature: 温度参数
        max_retries: 最大重试次数

    Returns:
        解析后的 JSON 字典，失败返回 None
    """
    content = call_llm_with_retry(
        prompt=prompt,
        system_prompt=system_prompt,
        model=model,
        temperature=temperature,
        max_retries=max_retries
    )

    if not content:
        return None

    return extract_json(content)


def call_llm_json_array(
    prompt: str,
    system_prompt: str = None,
    model: str = None,
    temperature: float = 1.0,
    max_retries: int = 2
) -> Optional[list]:
    """
    调用 LLM 并自动解析 JSON 数组响应

    Args:
        prompt: 用户提示词
        system_prompt: 系统提示词
        model: 模型名称
        temperature: 温度参数
        max_retries: 最大重试次数

    Returns:
        解析后的 JSON 列表，失败返回 None
    """
    content = call_llm_with_retry(
        prompt=prompt,
        system_prompt=system_prompt,
        model=model,
        temperature=temperature,
        max_retries=max_retries
    )

    if not content:
        return None

    return extract_json_array(content)
