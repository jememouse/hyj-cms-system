import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.workflow import BaseWorkflow
from agents.trend_hunter import TrendHunterAgent

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TrendWorkflow(BaseWorkflow):
    """
    Step 1：热点发现工作流

    fetch_jobs  → 读取 box_artist_config.json 作为种子词配置（单任务）
    process_job → TrendHunterAgent 搜索+分析，返回话题列表
    on_success  → StateBus.push_new_topics() 去重入库并同步 Google Sheet
    """

    def __init__(self):
        super().__init__("TrendWorkflow")
        self.agent = TrendHunterAgent()

    def fetch_jobs(self) -> list:
        config_file = os.path.join(BASE_DIR, 'box_artist_config.json')
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                return [json.load(f)]
        return [{"mining_seeds": ["包装", "礼盒"]}]

    def process_job(self, job: dict):
        return self.agent.hunt_and_analyze(job)

    def on_success(self, job: dict, topics: list):
        self.bus.push_new_topics(topics)
