#!/usr/bin/env python
#-*- coding: utf-8 -*-

"""
Francisco Javier Santacruz López-Cepero (C)
21-12-2011

File tree diff.
Generate a diff for two file hierarchies by inode.

side 1
< path (inode)

side 2
> path (inode)
"""

import os
import sys

import logging
from optparse import OptionParser

_LOGGING_FMT_ = '%(asctime)s %(levelname)-8s %(message)s'

def error(msg, is_exit=True):
    logging.error(msg)
    if is_exit:
        sys.exit(1)

def human_format(bytes):
    """
    Convert byte size to a human readable unit.
    Returns (size,unit)
    size between 1 and 1023
    unit in (B, KB, MB, GB, PB)
    """
    units = ('B', 'KB', 'MB', 'GB', 'PB')
    exp = 0
    while bytes > 1024 and exp < len(units):
        bytes /= 1024.0
        exp += 1

    return bytes, units[exp]


def main(opts, args):
    sides = len(args)
    bothsides = -1
    itable = dict()

    # Walk directories saving inodes and paths
    for side in range(sides):
        for root, dirs, files in os.walk(args[side]):
                # New inode, add directly
                # if the inode already exists, check side
                if inode not in itable:
            for fpath in [os.path.join(root, f) for f in files]:
                inode = os.lstat(fpath).st_ino

                    itable[inode] = [side, [file]]
                else:
                    if itable[inode][0] != side:
                        itable[inode] = [-1]
                    else:
                        itable[inode][1].append(file)

    # Print results
    # Only show files owned by one side.
    symbol = ('<', '>')
    for side in range(sides):
        print args[side]
        for inode, row in itable.iteritems():
            itside = row[0]
            if itside != side:
                continue

            files = row[1]
            for fpath in files:
                print "{0} {1} {2}".format(symbol[side], inode, fpath)

if __name__ == "__main__":
    parser = OptionParser()

    parser.add_option("-v", "--verbose", dest="verbose",
                      action="count", default=0,
                      help="Verbosity. Default silent. -v (info) -vv (debug)")

    parser.set_usage("Usage: [options] db.sqlite3")

    (opts, args) = parser.parse_args()

    # Configure logging
    logging_levels = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}
    level = logging_levels[opts.verbose if opts.verbose < 3 else 2]
    logging.basicConfig(level=level, format=_LOGGING_FMT_)

    if len(args) != 2:
        logging.error("Missing arguments")
        parser.print_help()
        sys.exit(1)

    main(opts, args)
