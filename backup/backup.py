#!/usr/bin/env python
#-*- coding: utf-8 -*-
"""

Javier Santacruz 16/07/2011

Backup script, rsync based.
Creates a backup scheme where each backup is a standalone copy of its contents.
Copies are shared hard links, saving lots of space.
Supports ssh and rsync format. Reads config data from yaml files.
"""

import os
import sys
import yaml
import time
import subprocess
import logging
import shutil

from optparse import OptionParser

_COPY_DATE_FMT_ = "%Y%m%d-%H%M"  # year month day - hour minute
_WEEK_DATE_FMT_ = "week-%Y-%W"  # year - week of year
_LOGGING_FMT_ = '%(asctime)s %(levelname)-8s %(message)s'


def error(msg, is_exit=True):
    logging.error(msg)
    if is_exit:
        sys.exit()


def get_copy_date():
    """Returns date in the script format"""
    return time.strftime(_COPY_DATE_FMT_)


def get_copy_week(copy):
    """Returns the week date in the script format"""
    return time.strftime(_WEEK_DATE_FMT_, time.strptime(copy, _COPY_DATE_FMT_))


def get_empty_plan():
    """Returns a basic empty plan"""
    return {"origins": [], "dest": "", "rotate_max": 10}


def get_ssh_origins(user, host, origins):
    """Formats each copy target for ssh protocol access"""
    return ["%s@%s:%s" % (user, host, origin) for origin in origins]


def get_rsync_origins(module, host, origins):
    """Formats each copy target for rsync protocol access"""
    return ["%s::%s/%s" % (host, module, origin) for origin in origins]

def rsync(origins, dest, args):
    """ Executes rsync for origins to dest with the provided options.  """
    line = ["rsync"] + args + origins + [dest]
    logging.debug("Rsync call: %s " % " ".join(line))
    return subprocess.call(line)


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
        logging.debug("Couldn't unlink last pointer at %s" % last)

    try:
        os.symlink(dest, last)
    except OSError:
        logging.warning("Couldn't link %s to last pointer at %s"
                        % (dest, last))
    else:
        logging.info("Linked %s last pointer to %s" % (dest, last))

def read_config(opts, path):
    """Reads a plan in yaml"""
    with open(path, "r") as file:
        try:
            plan = yaml.load(file, Loader=yaml.Loader)
        #except yaml.scanner.ScannerError, e:
        except yaml.error.YAMLError, e:
            logging.error("Error parsing config file <%s>: %s" % (path, e))
            return
        else:
            logging.info("Reading config from <%s>" % path)

    for arg in ('origins', 'excludes', 'rsync_args'):
        if arg in plan and plan[arg] is not None:
            getattr(opts, arg).extend(plan[arg])

    # Get missing opts options from the plan
    for arg in ('dest', 'origin_host', 'origin_module', 'origin_user',
                'rotate_max', 'logfile', 'verbose'):
        if not getattr(opts, arg): 
            setattr(opts, arg, plan[arg] if arg in plan else "")

    # Add host and module/ssh info to origins if needed
    if opts.origin_host and opts.origin_module:
        opts.origins = get_rsync_origins(opts.origin_module,
                                         opts.origin_host,
                                         opts.origins)
    elif opts.origin_host and opts.origin_user:
        opts.origins = get_ssh_origins(opts.origin_user,
                                       opts.origin_host,
                                       opts.origins)

def backup(origins, dest, opts):
    """Performs the backup from origins to dest using options"""
    copy_name = get_copy_date()  # Name for the copy
    copy_dir = os.path.join(dest, copy_name)  # Where to store
    last = os.path.join(dest, "last")  # last copy pointer

    args = ["-az", "--delete", "--delete-excluded", "--itemize-changes",
                 "--max-size", opts.max_size, "--link-dest", last]
    args.extend(opts.rsync_args)

    # Append --exclude before each exclude path, for rsync
    args.extend(format_exclude_args(opts.excludes))

    if opts.pre_hook:
        logging.info("Calling pre-hook: %s" % opts.pre_hook)
        retval = subprocess.call([opts.pre_hook, opts.dest, opts.logfile] +
                                 origins)
        logging.info("post-hook finished with return value: %i" % retval)

    logging.info("Starting backup for %s to %s"
                 % (" ".join(origins), copy_dir))

    try:
        retval = rsync(origins, copy_dir, args)
    except KeyboardInterrupt:
        logging.info("Rsync cancelled by user.")
        retval = 20

    if retval == 0 and not opts.test:
        logging.info("Done. Copy successful at %s" % copy_dir)
    elif opts.test:
        logging.info("Done. Test copy finished. Rsync exited with code: %i." %
                     retval)
    else:
        logging.error("Copy failed. Rsync exited with code: %i" % retval)

    # Make new last pointer whether successful or a new dir was created.
    if not opts.test:
        if retval == 0 or copy_name in os.listdir(dest):
            reset_last_pointer(last, copy_dir)

    if opts.post_hook:
        logging.info("Calling post-hook: %s" % opts.post_hook)
        retval = subprocess.call([opts.post_hook, opts.dest,
                                  opts.logfile, retval] + opts.origins)
        logging.info("post-hook finished with return value: %i" % retval)

def rotate(dest, max):
    """Stores old copies into weekly directories"""
    copies = filter_copy_names(os.listdir(dest))

    logging.info("Found %i of max %i copies in %s"
                 % (len(copies), max_copies, dest))
    logging.debug("Copies to rotate: %s" % " ".join(copies))

    if len(copies) < max:
        logging.info("Not enough copies (%d) to perform rotation (%d needed)."\
                     % (len(copies), max))
        return

    logging.info("Performing rotation at %s" % dest)

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

        try:
            os.mkdir(week_dir)
        except OSError:
            pass
        else:
            logging.info("Created week_dir %s" % week_dir)
            n_weeks += 1

        try:
            shutil.move(copy_dir, week_dir)
        except shutil.Error, e:
            logging.error("Couln't copy to week dir when rotating: %s" % e)
        else:
            logging.debug("Moving %s to %s" % (copy_dir, week_dir))
            n_moves += 1

    if last_copy:
        last_pointer = os.path.join(dest, "last")
        reset_last_pointer(last_pointer, last_copy)

    logging.info("Rotation performed. %i copies moved. %i dirs created." %
                 (n_moves, n_weeks))

def main(opts, args):
    action = args[0]

    if action == "backup":
        if not opts.origins:
            error("Action [backup] needs origins.")
        backup(opts.origins, opts.dest, opts)
    elif action == "rotate":
        rotate(opts.dest, opts.rotate_max)
    elif action == "test":
        opts.rsync_args.append("--dry-run")
        backup(opts.origins, opts.dest, opts)

if __name__ == "__main__":
    parser = OptionParser()

    parser.add_option("-p", "--plan", dest="plan",
                      action="store", default="",
                      help="Backup plan definition.")

    parser.add_option("-o", "--origin", dest="origins",
                      action="append", default=[],
                      help="Add location to backup.")

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
                      help="Exclude patterns.")

    parser.add_option("-s", "--max-size", dest="max_size",
                      action="store", default="500M", 
                      help="Exclude big files. Default 500M.")

    parser.add_option("-a", "--rsync-args", dest="rsync_args",
                      action="append", default=[],
                      help="Extra args for rsync.")

    parser.add_option("-l", "--logfile", dest="logfile", action="store",
                      default="", help="Path to logfile to store log. Will log"
                      " to stdout if unset.")

    parser.add_option("-j", "--pre-hook", dest="pre_hook", action="store",
                      default="", help="Order to be called before backup.")

    parser.add_option("-k", "--post-hook", dest="post_hook", action="store",
                      default="", help="Order to be called after the backup.")

    parser.add_option("-v", "--verbose", dest="verbose",
                      action="count", default=0,
                      help="Verbosity. Default silent. -v (info) -vv (debug)")

    parser.set_usage("%prog Usage: [options] [--plan plan] backup|rotate|test")

    (opts, args) = parser.parse_args()

    opts.logfile_from_console = opts.logfile
    opts.verbose_from_console = opts.verbose

    logging_levels = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}
    level = opts.verbose if opts.verbose < 3 else 2
    logging.basicConfig(level=logging_levels[level], 
                        format=_LOGGING_FMT_, 
                       filename=opts.logfile)

    # Check arguments
    if len(args) != 1:
        parser.print_help()
        error("Action needed: backup|rotate|test")

    if args[0] not in ("backup", "rotate", "test"):
        parser.print_help()
        error("Unknown action %s. Must be: backup|rotate|test" % args[0])

    opts.test = (args[0] == "test")

    read_config(opts, opts.plan)

    # If logfile or verbose has been obtained from config, reconfigure logging.
    if opts.logfile != opts.logfile_from_console\
       or opts.verbose != opts.verbose_from_console:
        level = opts.verbose if opts.verbose < 3 else 2
	logging.basicConfig(level=logging_levels[level], 
			format=_LOGGING_FMT_, 
			filename=opts.logfile)

    if not opts.dest:
        error("Destination -d/--dest is mandatory.")

    main(opts, args)
