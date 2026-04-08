import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from workflows.social_workflow import SocialWorkflow


def run():
    SocialWorkflow().run()


if __name__ == "__main__":
    run()
