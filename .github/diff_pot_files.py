#! /usr/bin/env python3

"""
Super small script for github action to detect if 2 .pot files have changed for
github/workflows/auto_messages_pot.yml
"""

import sys
from babel.messages.pofile import PoFileParser


def load_pot_file(file_path):
    poparser = PoFileParser({})
    poparser.parse(open(file_path))
    return poparser.catalog


def main():
    file_1 = load_pot_file(sys.argv[1])
    file_2 = load_pot_file(sys.argv[2])

    if [x for x in file_1.keys() if x] == [x for x in file_2.keys() if x]:
        print("false")
    else:
        print("true")


if __name__ == "__main__":
    main()
