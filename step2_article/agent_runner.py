import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from workflows.article_workflow import ArticleWorkflow


def run():
    ArticleWorkflow().run()


if __name__ == "__main__":
    run()
