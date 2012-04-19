#!/usr/bin/env python
#-*- coding: utf-8 -*-
"""

Javier Santacruz 16/07/2011

Backup script, rsync based.
Creates a backup scheme where each backup is a standalone copy of its contents.
Copies shares hard links, saving lots of space.
Reads config data from yaml files.
"""

import os
import sys
import yaml
import time
import subprocess
import logging
import shutil

from collections import Iterable
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


def filter_copy_names(names):
    """Returns only names that are valid copy directory names."""
    def get_name(name):
        try:
            time.strptime(name, _COPY_DATE_FMT_)
        except ValueError:
            return False
        else:
            return True

    return filter(get_name, names)


def format_exclude_args(excludes):
    """Generates command line exclude arguments for rsync"""
    return [e for sl in zip(["--exclude"] * len(excludes), excludes)
              for e in sl]


def reset_last_pointer(last, dest):
    """Sets the last link to the las copy made"""
    try:
        os.unlink(last)
    except OSError:
        logging.debug("Couldn't unlink last pointer at {0}".format(last))

    try:
        os.symlink(dest, last)
    except OSError:
        logging.warning("Couldn't link {0} to last pointer at {1}"
                        .format(dest, last))
    else:
        logging.info("Linked {0} last pointer to {1}".format(dest, last))


def read_config(path):
    """Reads a plan in yaml"""
    with open(path, "r") as pfile:
        try:
            plan = yaml.load(pfile, Loader=yaml.Loader)
        except yaml.error.YAMLError, e:
            logging.error("Error parsing config file <{0}>: {1}"
                          .format(path, e))
            return
        else:
            logging.info("Reading config from <{0}>".format(path))

        if not isinstance(plan, dict):
            logging.error("Error parsing config file <{0}>: {1}"
                          .format(path, e))
            return None

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
    print "Option Name\tValue or list\tDefault value"
    for op in parser.option_list:
        optype = str(type(op.default))[7:-2]
        opdef = "''" if op.default == "" else op.default
        print fmtstr.format(op.dest, optype, opdef)


def backup(origins, dest):
    """Performs the backup from origins to dest using options"""
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
        logging.info("Done. Test copy finished. Rsync exited with code: %i." %
                     retval)
    elif retval == 0:
        logging.info("Done. Copy successful at %s" % copy_dir)
    else:
        logging.error("Copy failed. Rsync returned code: {0}".format(retval))

    # Make new last pointer whether successful or a new dir was created.
    if not opts.test:
        if retval == 0 or copy_name in os.listdir(dest):
            reset_last_pointer(last, copy_dir)

    if opts.post_hook:
        hookcall("post_hook", opts.dest, opts.logfile, retval, origins)


def rotate(dest, max_copies):
    """Stores old copies into weekly directories"""
    copies = filter_copy_names(os.listdir(dest))

    logging.info("Found {0} of max {1} copies in {2}"
                 .format(len(copies), max_copies, dest))
    logging.debug("Copies to rotate: {0}".format(" ".join(copies)))

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
            except OSError:
                pass
            else:
                logging.info("Created week_dir {0}".format(week_dir))
                n_weeks += 1

        try:
            shutil.move(copy_dir, week_dir)
        except shutil.Error, e:
            logging.error("Couln't copy to week dir when rotating: {0}"
                          .format(e))
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

    parser.add_option("-p", "--plan", dest="plan",
                      action="store", default="",
                      help="Backup plan definition.")

    parser.add_option("-o", "--origin", dest="origins",
                      action="append", default=[],
                      help="Add location to backup."
                      " Can be called multiple times")

    parser.add_option("-d", "--dest", dest="dest",
                      action="store", default="",
                          help="Where to store the backup.")

    parser.add_option("-m", "--max", dest="rotate_max",
                      action="store", default=10, type="int",
                      help="Max number of backups stored. Default 10.")

    parser.add_option("", "--host", dest="origin_host",
                      action="store", default="",
                      help="Host for origins if needed.")

    parser.add_option("-g", "--module", dest="origin_module",
                      action="store", default="",
                      help="Module for origins if needed.")

    parser.add_option("-u", "--user", dest="origin_user",
                      action="store", default="",
                      help="User for ssh origins if needed.")

    parser.add_option("-e", "--exclude", dest="excludes",
                      action="append", default=[],
                      help="Exclude patterns. Can be called multiple times")

    parser.add_option("-s", "--max-size", dest="max_size",
                      action="store", default="500M",
                      help="Exclude big files. Default 500M.")

    parser.add_option("-a", "--rsync-args", dest="rsync_args",
                      action="append", default=[],
                      help="Extra args for rsync."
                      " Can be called multiple times")

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
                      default=0, help="Verbosity. Default silent. -v (info) "
                      " -vv (debug)")

    parser.set_usage("%prog Usage: [options] [--plan plan] backup|rotate|test")

    (opts, args) = parser.parse_args()

    # Options that conserve its default value
    # They haven't been set by the user in the command line
    ffun = lambda o: o.dest is not None and getattr(opts, o.dest) == o.default
    opts.defaultopts = filter(ffun, parser.option_list)

    opts.logfile_from_console = opts.logfile
    opts.verbose_from_console = opts.verbose

    logging_levels = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}
    level = opts.verbose if opts.verbose < 3 else 2
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
        error("Action needed: backup|rotate|test")

    opts.action = args[0]

    if opts.action not in _ACTIONS_:
        parser.print_help()
        error("Unknown action %s. Actions: backup|rotate|test" % opts.action)

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
