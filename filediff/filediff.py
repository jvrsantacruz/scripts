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
            files = [":".join(files)]

        if not opts.nolist:
            for fpath in files:
                data['path'] = fpath
                print formatstr.format(**data)

    if opts.count:
        format, unit = human_format(count) if opts.human else (count, 'B',)
        formatn = "Total: {0}{{1}}".format("{0:.2f}" if opts.human else "{0}")
        print formatn.format(format, unit)

def check_args(opts, args):
    """
    Checks given directories in args
    Arguments must be readable directories in the same partition.
    """
    # Check wether arguments are readable directories
    for side, dpath in enumerate(args):
        if not os.path.isdir(dpath):
            error("Argument '{0}' it is not readable or its not a directory"\
                  .format(dpath))

        # Remove trailing '/', it makes posterior basename to fail
        if dpath.endswith("/"):
            args[side] = dpath[:-1]

    # Check wether directories are in the same device
    # otherwise inodes are not comparable
    stats = [os.lstat(dpath) for dpath in args]
    if stats[0].st_dev != stats[1].st_dev:
        error("Directories '{0}' and '{1}' are not in the same device"\
              .format(args[0], args[1]))

    # If both are the same directory, no difference is possible. Finish.
    if stats[0].st_ino == stats[1].st_ino:
        for side in range(len(args)):
            if opts.printside[side]:
                list_changes(side, {}, opts, args)
        sys.exit(0)

def statfile(fpath):
    """
    Performs stat over the given path. Dereferences links if needed.
    Returns (inode, size, nlink)
    """
    fstat = os.lstat(fpath)

    # If dereference links is active, and we find a link
    # grab the pointed file instead of the linkfile
    if opts.link and os.path.islink(fpath):
        lpath = os.path.realpath(fpath)
        lstat = os.lstat(lpath)
        if fstat.st_dev != lstat.st_dev:
            logging.warning("Couldn't dereference '{0}',"
                            "it points to a external device".format(fpath))
        else:
            fpath = lpath
            fstat = lstat

    return fstat.st_ino, fstat.st_size, fstat.st_nlink

def main(opts, args):
    """
    Walks two given directories and prints a diff-like list of files which are
    only in one of them, optionally printing inode and sizes and dereferencing links.
    """
    sides = len(args)
    bothsides = -1
    itable = dict()
    itable_singles = list()

    # Walk directories saving inodes and paths
    for side in range(sides):
        for root, dirs, files in os.walk(args[side]):
                fstat = os.lstat(fpath)

                # If dereference links is active, and we find a link
                # grab the pointed file instead of the linkfile
                if opts.link and os.path.islink(fpath):
                    lpath = os.path.realpath(fpath)
                    lstat = os.lstat(lpath)
                    if fstat.st_dev != lstat.st_dev:
                        if opts.verbose:
                            logging.warning("Couldn't dereference '{0}',"
                                            "points to a external device".\
                                            format(fpath))
                    else:
                        fpath = lpath
                        fstat = lstat

                inode = fstat.st_ino
                size = fstat.st_size
                nlink = fstat.st_nlink
            for fpath in [os.path.join(root, f) for f in files + dirs]:

                # Store and process inode
                # when nlink is 1, this inode can't appear in any other dir
                # so we save it to another place to decrease itable size.
                entry = None if nlink == 1 else itable.get(inode)
                datarow = [side, [fpath]]
                if opts.size or opts.count:
                    datarow.append(size)

                # nlink is 1: save the inode into singles list.
                # New inode: store path (if nlink is 1, we can assure it's uniq)
                # inode exists owned by other side: discard data and mark it
                # inode exists in same side: add hard link path
                if nlink == 1:
                    itable_singles.append((inode, datarow,))
                elif entry is None:
                    itable[inode] = datarow
                elif entry[0] == bothsides:
                    pass
                elif entry[0] != side:
                    itable[inode] = [bothsides]
                else:  # entry[0] == side
                    itable[inode][1].append(fpath)

    # Remove bothsiders and append singles
    itable = dict([(inode,data,) for inode,data in itable.items()\
              if data[0] != bothsides])
    itable.update(itable_singles)

    for side in range(sides):
        if opts.printside[side]:
            list_changes(side, itable, opts, args)

if __name__ == "__main__":
    parser = OptionParser()

    parser.add_option("-v", "--verbose", dest="verbose",
                      action="count", default=0,
                      help="Verbosity. Default silent. -v (info) -vv (debug)")

    parser.add_option("-i", "--inode", dest="inode",
                      action="store_true", default=False,
                      help="Show file inodes.")

    parser.add_option("-g", "--group", dest="group",
                      action="store_true", default=False,
                      help="Group paths by inode. Multiple paths in one line")

    parser.add_option("-s", "--size", dest="size",
                      action="store_true", default=False,
                      help="Show file sizes")

    parser.add_option("-c", "--count", dest="count",
                      action="store_true", default=False,
                      help="Compute difference sizes")

    parser.add_option("-u", "--human", dest="human",
                      action="store_true", default=False,
                      help="Human readable sizes")

    parser.add_option("-L", "--link", dest="link",
                      action="store_true", default=False,
                      help="Dereference symbolic links")

    parser.add_option("-l", "--left", dest="right",
                      action="store_false", default=True,
                      help="Only left side. Don't print right side.")

    parser.add_option("-r", "--right", dest="left",
                      action="store_false", default=True,
                      help="Only print right side. Don't print left side.")

    parser.add_option("-n", "--nolist", dest="nolist",
                      action="store_true", default=False,
                      help="Don't print file list.")

    parser.set_usage("Usage: [options] DIR DIR")

    (opts, args) = parser.parse_args()

    # Configure logging
    logging_levels = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}
    level = logging_levels[opts.verbose if opts.verbose < 3 else 2]
    logging.basicConfig(level=level, format=_LOGGING_FMT_)

    if len(args) < 2:
        parser.print_help()
        error("Missing directories to check.")

    if len(args) > 2:
        parser.print_help()
        error("Too many directories to check.")

    opts.printside = (opts.left, opts.right)

    check_args(opts, args)
    main(opts, args)
