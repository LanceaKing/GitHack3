import os


class Config:
    basedir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dist = os.path.join(basedir, 'dist')
    ua_file = os.path.join(basedir, 'doc', 'user-agents.txt')
