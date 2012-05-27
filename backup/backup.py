#!/usr/bin/env python
#-*- coding: utf-8 -*-
"""
Backup script, rsync based.
Creates a backup scheme where each backup is a standalone copy of its contents.
Copies shares hard links, saving lots of space.
Reads config data from yaml files.

Copyright © 2012 Javier Santacruz. All Rights Reserved.
"""

import os
import sys
import yaml
import time
import subprocess
import logging
import shutil
import hashlib

from collections import Iterable, defaultdict
from optparse import OptionParser

_COPY_DATE_FMT_ = "%Y%m%d-%H%M"  # year month day - hour minute
_WEEK_DATE_FMT_ = "week-%Y-%W"  # year - week of year
_LOGGING_FMT_ = '%(asctime)s %(levelname)-8s %(message)s'
_ACTIONS_ = ("backup", "rotate", "test")


def error(msg, is_exit=True):
    logging.error(msg)
    if is_exit:
        sys.exit()


def get_copy_date():
    "Returns date in the script format"
    return time.strftime(_COPY_DATE_FMT_)


def get_copy_week(copy):
    "Returns the week date in the script format"
    return time.strftime(_WEEK_DATE_FMT_, time.strptime(copy, _COPY_DATE_FMT_))


def get_ssh_origins(user, host, origins):
    "Formats each copy target for ssh protocol access"
    return ["%s@%s:%s" % (user, host, origin) for origin in origins]


def get_rsync_origins(module, host, origins):
    "Formats each copy target for rsync protocol access"
    return ["%s::%s/%s" % (host, module, origin) for origin in origins]


def human_format(nbytes):
    """ Convert byte sizes to a human readable unit.
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


def hookcall(hookname, *extras):
    "Executes a hook call"
    exename = getattr(opts, hookname)[0]
    callargs = getattr(opts, hookname)[1:]
    logging.info("Calling {0}".format(hookname))
    if not getattr(opts, hookname + "_args"):
        syscall(exename)
    else:
        syscall(exename, callargs)


def syscall(command, *arguments):
    "Executes a system call and returns its execution return value"
    cmd = [command]
    for arg in arguments:
        if not isinstance(arg, str) and isinstance(arg, Iterable):
            cmd.extend(arg)
        else:
            cmd.append(arg)
    logging.info("System call: {0}".format(" ".join(cmd)))
    return subprocess.call(cmd)


def filter_date_names(names, dateformat):
    "Returns only names that are valid 'dateformat' names."
    def get_name(name):
        try:
            time.strptime(name, dateformat)
        except ValueError:
            return False
        else:
            return True

    return filter(get_name, names)


def format_exclude_args(excludes):
    "Generates command line exclude arguments for rsync"
    return [exclude for excludepair
            in zip(["--exclude"] * len(excludes), excludes)
            for exclude in excludepair]


def reset_last_pointer(last, dest):
    "Sets the last link to the las copy made"
    try:
        os.unlink(last)
    except OSError, err:
        logging.debug("Couldn't unlink last pointer at {0}: {1}"
                      .format(last, err))

    try:
        os.symlink(dest, last)
    except OSError, err:
        logging.warning("Couldn't link {0} to last pointer at {1}: {2}"
                        .format(dest, last, err))
    else:
        logging.info("Linked {0} last pointer to {1}".format(dest, last))


def open_config(path):
    "Reads and returns a plan config file in yaml format"
    if not path:
        return None

    plan = None
    with open(path, "r") as pfile:
        try:
            plan = yaml.load(pfile, Loader=yaml.Loader)
        except yaml.error.YAMLError, err:
            logging.error("Error parsing plan config file <{0}>: {1}"
                          .format(path, err))
            return
        else:
            logging.info("Reading config from <{0}>".format(path))

    if not isinstance(plan, dict):
        logging.error("Wrong format for plan config file <{0}>"
                      .format(path))
        return None

    return plan


def read_config(path):
    "Reads a plan in yaml"
    if not path:
        return

    plan = open_config(path)
    if plan is None:
        return

    # Read from plan all options with default value
    for option in [opt for opt in opts.defaultopts if opt.dest in plan]:
        if option.action == "append":
            getattr(opts, option.dest).extend(plan[option.dest])
        else:
            setattr(opts, option.dest, plan[option.dest])

    # Add host and module/ssh info to origins if needed
    if opts.origin_host and opts.origin_module:
        opts.origins = get_rsync_origins(opts.origin_module,
                                         opts.origin_host,
                                         opts.origins)
    elif opts.origin_host and opts.origin_user:
        opts.origins = get_ssh_origins(opts.origin_user,
                                       opts.origin_host,
                                       opts.origins)


def list_avail_plan_opts():
    "Lists options that can be used in a plan file"
    fmtstr = "{0}\t{1}\t{2}"
    print fmtstr.format('Option Name', 'Value or list', 'Default value')
    for op in parser.option_list:
        optype = str(type(op.default))[7:-2]
        opdef = "''" if op.default == "" else op.default
        print fmtstr.format(op.dest, optype, opdef)


def list_weekly(dest):
    """Finds weekly directories in dest
    returns a list with the copy directories within dest. Oldest first
    """

    weekdirs = []
    copydirs = []

    try:
        weekdirs = os.listdir(dest)
    except OSError, err:
        logging.error("Couldn't list directory {0}: {1}".format(dest, err))
        weekdirs = []

    for week in sorted(filter_date_names(weekdirs, _WEEK_DATE_FMT_)):
        copydirs.extend([os.path.join(dest, week, name) for name in
                    filter_date_names(copydirs, _COPY_DATE_FMT_)])

    return sorted(copydirs)


def list_copies(dest):
    """List all existent copies in dir and weekly subdirs.
    returns a list with the copy directories within dest. Oldest first
    """
    copydirs = []

    try:
        copydirs = os.listdir(dest)
    except OSError, err:
        logging.error("Couldn't list directory {0}: {1}".format(dest, err))
        copydirs = []

    copydirs = [os.path.join(dest, cdir) for cdir in
                filter_date_names(copydirs, _COPY_DATE_FMT_)]
    copydirs.extend(list_weekly(dest))
    return sorted(copydirs)


def hashfile(fpath):
    "Calculates the hash hex string for the data in the file in the given path"
    sha1hash = hashlib.sha1()
    hexdigest = ''
    try:
        fhashfile = open(fpath, 'rb')
    except IOError:
        logging.warning("Couldn't open {0} for hashing".format(fpath))
    else:
        block = fhashfile.read(524288)  # Blocks of 512KB
        while block:
            sha1hash.update(block)
            block = fhashfile.read(524288)

        hexdigest = sha1hash.hexdigest()
    finally:
        fhashfile.close()

    return hexdigest


def delete_paths(fpaths):
    "Unlinks each path and returns a list of paths successfully removed"
    def __delete(fpath):
        try:
            logging.info("Removing repeated file {0}...".format(fpath))
            os.unlink(fpath)
        except OSError, err:
            logging.warning("Couldn't remove {0} when checking: {1}"
                          .format(fpath, err))
            return False
        else:
            return True

    return filter(__delete, fpaths)


def link_to_file(fpaths, master_path):
    """Links each path to master and adds the path to master fileentry
    returns the paths sucessfully linked"""
    # Link it to the first one with the same data instead
    def __link(fpath):
        try:
            logging.info("Linking {0} to {1}...".format(fpath, master_path))
            os.link(master_path, fpath)
        except OSError, err:
            logging.warning("Couldn't link {0} to {1} when checking."
                            " Caution! Some data might be lost!: {1}"
                            .format(fpath, master_path, err))
            return False
        else:
            return True

    return filter(__link, fpaths)


def group_by_hash(fileentries):
    "Returns a list of list containing fileentries with the same hash"
    # Calculate all file hashes
    for fentry in fileentries:
        if not fentry[2]:  # Check fentry hash
            # Warn the user if the hashing its going to take some time
            if fentry[1] > 1024 ** 3:
                size, unit = human_format(fentry[1])
                logging.info("Hashing big file of size {0:.2f}{1}: {2}"
                             .format(size, unit, fentry[-1][0]))
            fentry[2] = hashfile(fentry[-1][0])  # Get first path

    # Only entries with hash (hash, fileentry)
    fileentries = [(fe[2], fe) for fe in fileentries if fe[2]]

    # Group by hash
    groups = defaultdict(list)
    for fhash, fentry in fileentries:
        groups[fhash].append(fentry)

    # Only groups with coincidences
    return filter(lambda g: len(g) > 1, groups.values())


def unify_files(group):
    """Takes a list of file entries and links them all to the same inode.
    Modifies the chosen inode file entry to add the new linked paths.
    Returns a list of deleted inodes"""
    deleted_inodes = set()  # deleted inodes

    # Chose the most linked fentry to link the rest to it
    firstentry = max(group, key=lambda g: len(g[-1]))
    group.remove(firstentry)
    firstpath = firstentry[-1][0]

    # For each fentry in the group,
    # 1. Remove all file links
    # 2. Link them back to the master fentry in group
    # 3. Save path on master and remove it from the fentry
    # 4. If all links for a given fentry were unlinked and linked,
    #    the doesn't exists any longer, store the deleted inode
    for fentry in group:
        deleted_paths = delete_paths(fentry[-1])
        deleted_paths = link_to_file(deleted_paths, firstpath)
        fentry[-1][:] = list(set(fentry[-1]) - set(deleted_paths))
        firstentry[-1].extend(deleted_paths)
        if not fentry[-1]:
            deleted_inodes.add(fentry[0])  # Add inode if all links were remvd

    return list(deleted_inodes)


def check_files_samesize(samesize_fentries, repare):
    """Checks files of the same size and optionally unyfies them
    Returns number of files removed, freed size (bytes)"""
    # If there is more than one file with same size, check data
    # grouping them together if they're identical, unifying them
    groupbyhash = group_by_hash(samesize_fentries)
    if not groupbyhash:
        return

    entrysize = groupbyhash[0][0][1]  # Get size from first group's first entry
    fmtentrysize, unit = human_format(entrysize)
    for group in groupbyhash:
        logging.info("Same content in {0} different files of size {1}{2}:"
                     .format(len(group), fmtentrysize, unit))
        for fentry in group:
            morethan5 = '...' if len(fentry[-1]) > 5 else ''
            logging.info("\tinode: {0} link paths: {1}{2}"
                         .format(fentry[0], fentry[-1][:5], morethan5))

        nremoved = 0
        if repare:
            logging.info("Unifying {0} files to one".format(len(group)))
            nremoved = len(unify_files(group))
            fmtentrysize = entrysize * nremoved
            fmtentrysize, unit = human_format(fmtentrysize)
            logging.info("{0} files unified freeing {1}{2}"
                         .format(nremoved, fmtentrysize, unit))


def check_copies(dest):
    """
    Checks existent backups and solves data replication.
    Data replication is caused by files with the same contents, which for some
    reason, has been copied twice.
    """
    copydirs = list_copies(dest)

    def allpaths(root):
        "All files generator. root: a,b,c => ['root/a', 'root/b', 'root/c']"
        for root, dirs, files in os.walk(root):
            for filename in files:
                yield os.path.join(root, filename)

    # Store paths for later checking
    byinode = {}   # Store a file entry [inode, size, hash, paths]
    bysize = {}    # Relates file entries with same size

    for ndir, copydir in enumerate(copydirs):
        logging.info("Checking copy directory {0}/{1}: {2}"
                     .format(ndir + 1, len(copydirs), copydir))
        for fpath in allpaths(copydir):
            try:
                stat = os.stat(fpath)
            except OSError, err:
                logging.warning("Couldn't stat file {0}: {1}"
                                .format(fpath, err))
                continue

            inode, size = stat.st_ino, stat.st_size

            # Save it by inode
            fileentry = byinode.get(inode)
            if fileentry is None:
                fileentry = [inode, size, '', [fpath]]
                byinode[inode] = fileentry
            else:
                fileentry[-1].append(fpath)

            # If there is other files of the same size
            # they're perfect candidates to be indeed the same file
            # So we hash them, and if they're effectively identical,
            # link all paths to the most linked and remove the rest.
            entriesbysize = bysize.get(size)
            if entriesbysize is None:
                bysize[size] = {inode: fileentry}
            elif inode not in entriesbysize:
                entriesbysize[inode] = fileentry

                # Perform the checking as we go if dynamic_checking
                if opts.dynamic_checking:
                    check_files_samesize(entriesbysize.values(), opts.repare)

        logging.info("Found {0} different files in total".format(len(byinode)))

    # Check at the end if it is only repare and not dynamic_checking
    if not opts.dynamic_checking:
        for fentries in [fen for fen in bysize.values() if len(fen) > 1]:
            check_files_samesize(fentries.values(), opts.repare)


def backup(origins, dest):
    "Performs the backup from origins to dest using options"
    copy_name = get_copy_date()  # Name for the copy
    copy_dir = os.path.join(dest, copy_name)  # Where to store
    last = os.path.join(dest, "last")  # last copy pointer

    arguments = ["-az", "--delete", "--delete-excluded", "--itemize-changes",
                 "--max-size", opts.max_size, "--link-dest", last]
    arguments.extend(opts.rsync_args)

    # Append --exclude before each exclude path, for rsync
    logging.debug(opts.exclude)
    arguments.extend(format_exclude_args(opts.exclude))

    if opts.pre_hook:
        hookcall("pre_hook", opts.dest, opts.logfile, origins)

    logging.info("Starting backup for {0} to {0}"
                 .format(" ".join(origins), copy_dir))

    try:
        retval = syscall("rsync", origins, copy_dir, arguments)
    except KeyboardInterrupt:
        logging.info("Rsync cancelled by user.")
        retval = 20

    if opts.test:
        logging.info("Done. Test copy finished. Rsync exited with code: {0}."
                     .format(retval))
    elif retval == 0:
        logging.info("Done. Copy successful at {0}".format(copy_dir))
    else:
        logging.warning("Copy failed. Rsync returned code: {0}".format(retval))

    # Make new last pointer whether successful or a new dir was created.
    if not opts.test:
        if retval == 0 or copy_name in os.listdir(dest):
            reset_last_pointer(last, copy_dir)

    if opts.post_hook:
        hookcall("post_hook", opts.dest, opts.logfile, retval, origins)


def rotate(dest, max_copies):
    """Stores old copies into weekly directories"""
    copies = filter_date_names(os.listdir(dest), _COPY_DATE_FMT_)

    logging.info("Found {0} of max {1} copies in {2}"
                 .format(len(copies), max_copies, dest))

    if len(copies) < max_copies:
        logging.info("Not enough copies ({0}) to perform rotation ({1} needed)"
                     .format(len(copies), max_copies))
        return

    logging.info("Performing rotation at {0}".format(dest))

    # lexicographical sort makes most recent copy to be the last one
    copies.sort()

    # Move copies
    n_moves = 0
    n_weeks = 0
    last_copy = ""
    for copy in copies:
        copy_dir = os.path.join(dest, copy)
        week_dir = os.path.join(dest, get_copy_week(copy))
        last_copy = os.path.join(week_dir, copy)

        if not os.path.exists(week_dir):
            try:
                os.mkdir(week_dir)
            except OSError, err:
                logging.error("Couldn't create week dir: {0}".format(err))
                continue
            else:
                logging.info("Created week_dir {0}".format(week_dir))
                n_weeks += 1

        try:
            shutil.move(copy_dir, week_dir)
        except shutil.Error, err:
            logging.error("Couln't copy to week dir when rotating: {0}"
                          .format(err))
        else:
            logging.debug("Moving {0} to {1}".format(copy_dir, week_dir))
            n_moves += 1

    if last_copy:
        last_pointer = os.path.join(dest, "last")
        reset_last_pointer(last_pointer, last_copy)

    logging.info("Rotation performed. {0} copies moved. {1} dirs created."
                 .format(n_moves, n_weeks))


def main():
    if not opts.dest:
        error("Destination -d/--dest is mandatory.")

    if not opts.origins and (opts.backup or opts.test):
        error("Actions (backup, test) needs at least one origin directory.")

    if opts.backup:
        backup(opts.origins, opts.dest)
    elif opts.rotate:
        rotate(opts.dest, opts.rotate_max)
    elif opts.test:
        opts.rsync_args.append("--dry-run")
        backup(opts.origins, opts.dest)


if __name__ == "__main__":
    parser = OptionParser()

    parser.add_option("-p", "--plan", dest="plan", action="store", default="",
                      help="Backup plan definition.")

    parser.add_option("-o", "--origin", dest="origins", action="append",
                      default=[], help="Add location to backup. Can be called"
                      " multiple times")

    parser.add_option("-d", "--dest", dest="dest", action="store", default="",
                      help="Where to store the backup.")

    parser.add_option("-m", "--max", dest="rotate_max", action="store",
                      default=10, type="int", help="Max number of backups"
                      " stored. Default 10.")

    parser.add_option("", "--host", dest="origin_host", action="store",
                      default="", help="Host for origins if needed.")

    parser.add_option("-g", "--module", dest="origin_module", action="store",
                      default="", help="Module for origins if needed.")

    parser.add_option("-u", "--user", dest="origin_user", action="store",
                      default="", help="User for ssh origins if needed.")

    parser.add_option("-e", "--exclude", dest="exclude", action="append",
                      default=[], help="Exclude patterns. Can be called"
                      " multiple times")

    parser.add_option("-s", "--max-size", dest="max_size", action="store",
                      default="500M", help="Exclude big files. Default 500M.")

    parser.add_option("-a", "--rsync-args", dest="rsync_args", action="append",
                      default=[], help="Extra args for rsync. Can be called"
                      " multiple times")

    parser.add_option("-l", "--logfile", dest="logfile", action="store",
                      default="", help="Path to logfile to store log. Will log"
                      " to stdout if unset.")

    parser.add_option("-j", "--pre-hook", dest="pre_hook", action="store",
                      default="", help="Order to be called before backup.")

    parser.add_option("", "--pre-hook-args", dest="pre_hook_args",
                      action="store_true", default=False,
                      help="Pass to the pre_hook order the following"
                      " arguments: DEST_DIR," " LOGFILE, ORIGINS+")

    parser.add_option("-k", "--post-hook", dest="post_hook", action="store",
                      default="", help="Order to be called after the backup.")

    parser.add_option("", "--post-hook-args", dest="post_hook_args",
                      action="store_true", default=False, help="Pass to the"
                      " post_hook order the following arguments: DEST_DIR,"
                      " LOGFILE, ORIGINS+")

    parser.add_option("", "--list-opts", dest="list_opts", action="store_true",
                      default=False, help="Lists recognized plan options and"
                      " type.")

    parser.add_option("-v", "--verbose", dest="verbose", action="count",
                      default=1, help="Verbosity. Default warnings. -v (info) "
                      " -vv (debug)")

    parser.add_option("-q", "--quiet", dest="quiet", action="store_true",
                      default=False, help="Verbosity. Dont log warnings")

    parser.set_usage("%prog Usage: [options] [--plan plan] backup|rotate|test")

    (opts, args) = parser.parse_args()

    # Options that conserve its default value
    # They haven't been set by the user in the command line
    ffun = lambda o: o.dest is not None and getattr(opts, o.dest) == o.default
    opts.defaultopts = filter(ffun, parser.option_list)

    # store the values taken from the console
    opts.logfile_from_console = opts.logfile
    opts.verbose_from_console = opts.verbose

    if opts.quiet:
        opts.verbose = 0

    logging_levels = {0: logging.ERROR, 1: logging.WARNING,
                      2: logging.INFO, 3: logging.DEBUG}
    level = opts.verbose if opts.verbose < 4 else 3
    logging.basicConfig(level=logging_levels[level],
                        format=_LOGGING_FMT_,
                       filename=opts.logfile)

    # Direct options like --help and --list-opts finish here.
    if opts.list_opts:
        list_avail_plan_opts()
        sys.exit(0)

    # Check arguments
    if len(args) != 1:
        parser.print_help()
        print
        error("Action needed: {0}".format("|".join(_ACTIONS_)))

    opts.action = args[0]

    if opts.action not in _ACTIONS_:
        parser.print_help()
        print
        error("Unknown action {0}. Actions: {1}"
              .format(opts.action, "|".join(_ACTIONS_)))

    read_config(opts.plan)

    # Set opts.backup, opts.rotate and opts.test
    for action in _ACTIONS_:
        setattr(opts, action, action == opts.action)

    # If logfile or verbose has been obtained from config, reconfigure logging.
    if opts.logfile != opts.logfile_from_console\
       or opts.verbose != opts.verbose_from_console:
        level = opts.verbose if opts.verbose < 3 else 2
        logging.basicConfig(level=logging_levels[level],
                            format=_LOGGING_FMT_,
                            filename=opts.logfile)

    opts.pre_hook = opts.pre_hook.split()
    opts.post_hook = opts.post_hook.split()

    main()
