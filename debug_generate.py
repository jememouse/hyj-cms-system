import json
import sys
from skills.deep_writer import DeepWriteSkill

skill = DeepWriteSkill()
result = skill.execute({"topic": "测试文章标签生成", "category": "行业资讯"})
print(json.dumps(result, ensure_ascii=False, indent=2))
