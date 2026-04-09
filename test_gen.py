from skills.deep_writer import DeepWriteSkill
import json
skill = DeepWriteSkill()
input_data = {"topic": "测试文章", "category": "行业资讯"}
result = skill.execute(input_data)
print("KEYS RETURNED:", result.keys() if result else "None")
print("TAGS:", result.get("tags") if result else "N/A")
print("ONE LINE:", result.get("one_line_summary") if result else "N/A")
print("SUMMARY:", result.get("summary") if result else "N/A")
