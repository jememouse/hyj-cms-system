import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class BaseWorkflow:
    """
    工作流基类：定义标准的 fetch → process → commit 三段式执行节点。

    生命周期：
    1. fetch_jobs()   - 从 StateBus 获取待处理任务列表
    2. process_job()  - 调用 Agent 执行单个任务，返回结果
    3. on_success()   - 将结果写回 StateBus
    4. on_failure()   - 任务失败处理（默认只打印日志）

    子类必须实现 fetch_jobs / process_job / on_success。
    可选覆写 on_failure / _wait。
    如需完全自定义执行流（如 fan-out、带通知），可覆写 run()。
    """

    def __init__(self, name: str):
        self.name = name
        from core.state_bus import StateBus
        self.bus = StateBus()

    def fetch_jobs(self) -> list:
        """从状态总线获取待处理任务"""
        raise NotImplementedError

    def process_job(self, job: dict):
        """执行单个任务（调用 Agent），返回结果；返回 None 触发 on_failure"""
        raise NotImplementedError

    def on_success(self, job: dict, result):
        """任务成功：将结果写回状态总线"""
        raise NotImplementedError

    def on_failure(self, job: dict, error):
        """任务失败：默认打印日志，子类可覆写实现重试/状态回滚"""
        print(f"[{self.name}] ❌ 任务失败: {error}")

    def run(self):
        print(f"\n{'=' * 50}")
        print(f"🤖 启动 Workflow: {self.name}")
        print(f"{'=' * 50}\n")

        jobs = self.fetch_jobs()
        if not jobs:
            print(f"[{self.name}] 暂无待处理任务，退出。")
            return

        total = len(jobs)
        for idx, job in enumerate(jobs):
            title_preview = str(job.get('Topic') or job.get('Title') or '')[:30]
            print(f"\n--- [{idx + 1}/{total}] {title_preview}... ---")
            try:
                result = self.process_job(job)
                if result:
                    self.on_success(job, result)
                else:
                    self.on_failure(job, "无结果")
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.on_failure(job, e)
            self._wait()

    def _wait(self):
        """执行间的限速等待，子类覆写"""
        pass
