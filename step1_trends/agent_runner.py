import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from workflows.trend_workflow import TrendWorkflow


def run():
    TrendWorkflow().run()


if __name__ == "__main__":
    run()
