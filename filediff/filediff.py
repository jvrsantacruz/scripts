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

def list_changes(side, itable, opts, args):
    """Prints differences for a given side"""
    # Print results
    # Only show files owned by one side.
    symbol = ('<', '>')
    count = 0

    print os.path.basename(args[side])

    # Build format string
    formatstr ="{side}"
    if opts.inode:
        formatstr += " {inode}"
    if opts.size:
        if opts.human:
            formatstr += " {size:.2f}{unit}"
        else:
            formatstr += " {size}{unit}"
    formatstr += " {path}"

    data = {'side': symbol[side], 'path': ''}

    for inode, row in itable.iteritems():
        if row[0] != side:
            continue

        files = row[1]
        if opts.inode:
            data['inode'] = inode
        if opts.size:
            size, format = human_format(row[2]) if opts.human else (row[2], 'B',)
            data['size'] = size
            data['unit'] = format
        if opts.count:
            count += int(row[2])

        # Print each difference
        # If groups option provided, one line per inode, showing all paths.
        # Otherwise, one line per file
        if opts.group:
            data['path'] = ":".join(files)
            print formatstr.format(**data)
        else:
            for fpath in files:
                data['path'] = fpath
                print formatstr.format(**data)

    if opts.count:
        format, unit = human_format(count) if opts.human else (count, 'B',)
        formatn = "Total: {0}{{1}}".format("{0:.2f}" if opts.human else "{0}")
        print formatn.format(format, unit)

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

    for side in range(sides):
        if opts.printside[side]:
            list_changes(side, itable, opts, args)

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
