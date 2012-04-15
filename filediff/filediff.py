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
_BOTHSIDES_ = -1


def error(msg, is_exit=True):
    logging.error(msg)
    if is_exit:
        sys.exit(1)


def human_format(nbytes):
    """
    Convert byte sizes to a human readable unit.
    Returns (size,unit)
    size between 1 and 1023
    unit in (B, KB, MB, GB, PB)
    """
    units = ('B', 'KB', 'MB', 'GB', 'PB')
    exp = 0
    while nbytes > 1023 and exp < len(units):
        nbytes /= 1024.0
        exp += 1

    return nbytes, units[exp]


def make_formatstr():
    """
    Returns a proper entry list formatting line
    To be called as fmtstr.format(data)
    with following data: sides [inode] [size] path
    """
    formatstr = "{side}"
    if opts.inode:
        formatstr += " {inode}"
    if opts.size:
        if opts.human:
            formatstr += " {size:.2f}{unit}"
        else:
            formatstr += " {size}{unit}"
    formatstr += " {path}"

    return formatstr


def list_changes(side, itable):
    """Prints differences for a given side"""
    # Print results
    # Only show files owned by one side.
    totalsize = 0
    symbol = ('<', '>')

    formatstr = make_formatstr()
    data = {'side': symbol[side]}
    # Print the side-dir name as the title
    print os.path.basename(args[side])

    for inode, row in sorted(itable.iteritems(), key=lambda x: str(x[1][1])):
        if row[0] != side:
            continue

        files = row[1]
        if opts.inode:
            data['inode'] = inode

        # Output file size, properly formatted
        if opts.size:
            data['size'], data['unit'] = human_format(row[2])\
                    if opts.human else (row[2], 'B',)

        # Accumulate file size in bytes
        if opts.total:
            totalsize += int(row[2])

        # Print each difference as a file list
        # If groups option provided, one line per inode, showing all paths.
        # Otherwise, one line per file
        files = row[1]
        if opts.group:
            files = [":".join(files)]

        if not opts.nolist:
            for fpath in files:
                data['path'] = fpath
                print formatstr.format(**data)

    # Print totalsize for a side
    if opts.total:
        num, unit = human_format(totalsize) if opts.human else (totalsize, 'B')
        formatn = "Total: {0}{{1}}".format("{0:.2f}" if opts.human else "{0}")
        print formatn.format(number, unit)


def check_args():
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
                list_changes(side, {})
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


def datarow(side, path):
    """"Parses path and returns a proper data row
    returns (inode, size, nlink, data)
    """
    inode, size, nlink = statfile(path)
    data = [side, []]

    # Append size if needed
    if opts.size or opts.total:
        data.append(size)

    return inode, size, nlink, data


def difference(side, path, itable, singles):
    "Adds path to itable calculating difference inodes."
    inode, size, nlink, data = datarow(side, path)

    # nlink is 1, this inode can't appear in any other side
    if nlink == 1:
        data[1].append(path)
        singles.append((inode, data,))
        return

    # At this point we have a multiple linked file.
    # We use the table to keep track of this files,
    # and complete its data or mark it when we find the same.
    entry = itable.setdefault(inode, data)  # Sets data if inode is new
    eside = entry[0]
    if eside == side:          # append same sided link path (or itself)
        entry[1].append(path)
    elif eside != side:        # replace data for bothsides
        entry[0] = [_BOTHSIDES_]


def intersection(side, path, itable):
    """Adds path to itable calculating common inodes."""
    inode, size, nlink, data = datarow(side, path)

    # It cannot be twice in both trees if its not hardlinked.
    if nlink == 1:  # Ignore it.
        return

    entry = itable.setdefault(inode, data)  # Sets data if inode is new
    entry[1].append(path)
    if entry[0] != side:  # mark it as bothsides
        entry[0] = _BOTHSIDES_


def main():
    """
    Walks two given directories and prints a diff-like list of files which are
    only in one of them, optionally printing inode and sizes and dereferencing
    links.
    """
    sides = len(args)
    bothsides = -1
    itable = dict()
    itable_singles = list()

    # Walk directories saving inodes and paths
    for side in range(sides):
        for root, dirs, files in os.walk(args[side]):
            if opts.onlydirs:
                files = dirs
            elif opts.dirs:
                files.extend(dirs)

            for fpath in [os.path.join(root, f) for f in files]:
                inode, size, nlink = statfile(fpath)

                # Store and process inode
                # when nlink is 1, this inode can't appear in any other dir
                # so we save it to another place to decrease itable size.
                entry = None if nlink == 1 else itable.get(inode)
                data = [side, [fpath]]
                if opts.size or opts.count:
                    data.append(size)

                # nlink is 1: save the inode into singles list, it's unique
                # New inode: store path
                # inode exists owned by other side: discard data and mark it
                # inode exists in same side: add hard link path
                if nlink == 1:
                    itable_singles.append((inode, data,))
                elif entry is None:
                    itable[inode] = data
                elif entry[0] == bothsides:
                    pass
                elif entry[0] != side:
                    itable[inode] = [bothsides]
                else:  # entry[0] == side
                    itable[inode][1].append(fpath)

    # Remove bothsiders and append singles
    itable = dict([(inode, data,) for inode, data in itable.items()\
              if data[0] != bothsides])
    itable.update(itable_singles)

    for side in range(sides):
        if opts.printside[side]:
            list_changes(side, itable)

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

    parser.add_option("-t", "--total", dest="total",
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

    parser.add_option("-d", "--dirs", dest="dirs",
                      action="store_true", default=False,
                      help="Also count directories, not just regular files.")

    parser.add_option("-D", "--onlydirs", dest="onlydirs",
                      action="store_true", default=False,
                      help="Only count directories, not regular files.")

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

    check_args()
    main()
