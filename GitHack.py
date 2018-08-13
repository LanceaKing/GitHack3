#!/usr/bin/env python3.7
import argparse
import logging
import os
import sys

path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, path)

from lib import __version__
from lib.git import check_git
from lib.log import basicConfig
from lib.scan import GitScanner

try:
    import colorlog
except ImportError:
    colorlog = None

if colorlog:
    start = colorlog.escape_codes['bold_cyan']
    end = colorlog.escape_codes['reset']
else:
    start = end = ''

BANNER = rf"""{start}
  ____ _ _   _   _            _
 / ___(_) |_| | | | __ _  ___| | __
| |  _| | __| |_| |/ _` |/ __| |/ /
| |_| | | |_|  _  | (_| | (__|   <
 \____|_|\__|_| |_|\__,_|\___|_|\_\{{{__version__}}}
 A python3.7 '.git' folder disclosure exploit.
{end}"""


def main():
    print(BANNER)

    parser = argparse.ArgumentParser()
    parser.add_argument('url')
    parser.add_argument(
        '--debug',
        action='store_true',
        default=False,
        help='output verbose information')
    parser.add_argument(
        '--log',
        default=None,
        metavar='logfile',
        help='output verbose log to file')
    args = parser.parse_args()

    if args.debug:
        level = logging.DEBUG
    else:
        level = logging.INFO

    basicConfig(False, args.log, level)

    check_git()

    scanner = GitScanner(args.url)
    scanner.scan()


if __name__ == '__main__':
    main()
