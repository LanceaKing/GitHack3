import os


class Config:
    BASEDIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DIST = os.path.join(BASEDIR, 'dist')
    UA_FILE = os.path.join(BASEDIR, 'doc', 'user-agents.txt')
    THREADS = 8
    TIMEOUT = 8
