import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from workflows.publish_workflow import PublishWorkflow


def run():
    PublishWorkflow().run()


if __name__ == "__main__":
    run()
