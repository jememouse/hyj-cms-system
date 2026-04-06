import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import config, llm_utils

def check_llm():
    print("\n🔍 1. Testing Unified LLM Connection (via llm_utils)...")
    try:
        result = llm_utils.call_llm_with_retry("Hi", max_retries=1)
        if result:
             print(f"   ✅ LLM Response: {result}")
        else:
             print("   ❌ LLM Failed: Null response.")
    except Exception as e:
        print(f"   ❌ Execution Error: {e}")

if __name__ == "__main__":
    check_llm()
