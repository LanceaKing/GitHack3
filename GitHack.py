#!/usr/bin/env python3.7
import argparse
import logging
import os
import sys

path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, path)

from lib.scan import GitScanner
from lib.log import basicConfig
from lib.git import checkgit
from lib import BANNER


def main():
    print(BANNER)

    parser = argparse.ArgumentParser()
    parser.add_argument('url')
    parser.add_argument('--debug', action='store_true', default=False)
    parser.add_argument('--no-color', action='store_true', default=False)
    parser.add_argument('--log', default=None)
    args = parser.parse_args()

    if args.debug:
        level = logging.DEBUG
    else:
        level = logging.INFO

    basicConfig(args.no_color, args.log, level)

    checkgit()

    scanner = GitScanner(args.url)
    scanner.scan()


if __name__ == '__main__':
    main()
