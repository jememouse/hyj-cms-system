import os
from google import genai

# 1. 配置 API Key (使用环境变量提升安全性)
# 最佳实践提示：在生产环境中，强烈建议将 API Key 存放在环境变量中
API_KEY = os.getenv("GOOGLE_GENAI_API_KEY", "你的_GOOGLE_GENAI_API_KEY")

# 2. 初始化 Google GenAI 客户端
client = genai.Client(api_key=API_KEY)

# 3. 指定模型名称
MODEL_ID = "gemma-4-26b-a4b-it"

def generate_text(prompt: str) -> str:
    """
    使用 Google GenAI SDK 调用模型并返回生成的文本。
    """
    print(f"[Info] 正在调用模型 '{MODEL_ID}'...")
    try:
        # 使用新的 client.models.generate_content 官方标准 API
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"[Error] 调用发生错误: {e}"

if __name__ == "__main__":
    # 测试 Prompt
    test_prompt = "你好，请用中文简短地介绍一下你能做什么？"
    
    print("-" * 40)
    print(f"用户提问: {test_prompt}")
    print("-" * 40)
    
    # 执调用
    answer = generate_text(test_prompt)
    
    print("模型回复: \n")
    print(answer)
    print("-" * 40)
