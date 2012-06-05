#!/usr/bin/env python
#-*- coding: utf-8 -*-
"""
Copy files listed in a playlist to a directory.

Javier Santacruz 04/06/2011
"""

import os
import shutil
import random
from lxml import objectify
from optparse import OptionParser


class PIterable(object):
    "Base class for iterable playlists"

    def __init__(self, path):
        "Base constructor, sets self.path"
        self.path = path

    def __iter__(self):
        "Returns a new object to iterate with it"
        klass = type(self)
        return klass(self.path)


class Xspf(PIterable):
    "Iterate over a XSPF playlist file."

    ns = "http://xspf.org/ns/0/"

    def __init__(self, path):
        super(Xspf, self).__init__(path)
        self.root = objectify.parse(path).getroot()
        self.list = self.root.trackList.track[:]
        self.index = 0

    def next(self):
        "Returns title, absolute_path for every item on the list"
        if self.index == len(self.list):
            raise StopIteration

        # get title and remove initial file:///
        title = str(self.list[self.index].title)
        path = str(self.list[self.index].location)[7:]

        self.index += 1  # next track

        return title, path


class M3u(object):
    "Iterate over a M3U playlist file."

    ns = "#EXTM3U"

    def __init__(self, path):
        self.path = path
        self.base_path = os.path.dirname(self.path)
        self.file = open(self.path, "r")

        self.file.readline()  # Discard first line.

    def __iter__(self):
        return self

    def next(self):
        """Returns title, absolute_path for every item on the playlist.

        M3u objects have the following structure:

        #EXTM3U
        #EXTINF:342,Author - Song Title
        ../Music/song.mp3
        """

        # Get a line starting with #
        line = self.file.readline()

        # EOF found, stop Iteration.
        if not line:
            raise StopIteration

        # Read comments
        title = ""
        if line.startswith('#'):
            title = line.split(',', 1)[1]
            line = self.file.readline()

        path = os.path.join(self.base_path, line)[0:-1]

        return title, path


def detect_format(path):
    """Autodetects the format of a playlist file
    returns (m3u|xspf) or None if unkown
    """

    lfile = open(path, "r")
    header = lfile.readline(200)
    lfile.close()

    if M3u.ns in header:
        return "m3u"
    elif Xspf.ns in header:
        return "xspf"

    return None


def prefix_name(number, name, total):
    "Returns name prefixed with number. Filled with zeros to fit total"
    return "{0}_{1}".format(str(number).zfill(len(str(total))), name)


def sync_dirs(local_files, remote_dir, opts):
    """Copy a set files to a directory.
    If delete is set, will remove files in remote which are not in local.
    If link is set, will perform hard link instead of copy.
    If force is set, will copy all files ignoring if they're already in remote.
    """

    # Obtain file names in order to compare file subsets
    total_names = len(local_files)

    if opts.shuffle:
        random.shuffle(local_files)

    local_names = [os.path.basename(f) for f in local_files]

    if not opts.numbered:
        expected_names = local_names
    else:
        expected_names = [prefix_name(i + 1, f, total_names)
                             for i, f in enumerate(local_names)]

    remote_names = os.listdir(remote_dir)

    copy_files = [f for i, f in enumerate(local_files)
                  if opts.force or expected_names[i] not in remote_names]

    copied = deleted = 0

    # Remove files that are not in the playlist, if indicated.
    if opts.delete:
        delete_files = [os.path.join(remote_dir, f)
                        for f in remote_names
                        if f not in expected_names]

        print "Removing {0} files from {1}"\
                .format(len(delete_files, remote_dir))
        for f in delete_files:
            try:
                os.remove(f)
            except IOError, err:
                print "Error: Couldn't remove {0} from {1}: {2}"\
                    .format(os.path.basename(f), remote_dir, err)
            else:
                deleted += 1
                print "Removed {0}/{1}: {2}"\
                        .format(deleted, len(delete_files), f)

    if not opts.force:
        for f in set(remote_names).intersection(set(expected_names)):
            print "Skipping {0} which is already in {1}"\
                    .format(os.path.basename(f), remote_dir)

    # Copy files
    action = "Linking" if opts.link else "Copying"
    print "{0} {1} files to {2}".format(action, len(copy_files), remote_dir)
    for i, f in enumerate(copy_files):
        dest = os.path.basename(f)
        if opts.numbered:
            dest = prefix_name(i + 1, dest, total_names)
        dest = os.path.join(remote_dir, dest)

        op_result = link(f, dest) if opts.link else copy(f, dest)
        op_action = "Linked" if opts.link else "Copied"

        if op_result:
            copied += 1
            print "{0} {1}/{2}: {3}".format(op_action, copied,
                                            len(copy_files), f)

    print "{0} complete: {1} files copied, {2} files removed"\
            .format(action, copied, deleted)


def link(from_path, to_path):
    "Wrapper around os.link. Returns True/False on success/failure"
    try:
        os.link(from_path, to_path)
    except OSError, err:
        print "Error: Couldn't link {0} from {1} to {2}: {3}"\
               .format(os.path.basename(from_path), os.path.dirname(from_path),
                       to_path, err)
        return False
    else:
        return True


def copy(from_path, to_path):
    "Wrapper around shutil.copy. Returns True/False on success/failure"
    try:
        shutil.copy(from_path, to_path)
    except shutil.Error, err:
        print "Error: Couldn't copy {0} from {1} to {2}: {3}"\
                .format(os.path.basename(from_path),
                        os.path.dirname(from_path), to_path, err)
        return False
    except IOError, err:
        print "Error: Couldn't copy {0} from {1} to {2}: {3}"\
        .format(os.path.basename(from_path), os.path.dirname(from_path),
                to_path, err)
        return False

    return True


def main(pl_path, remote_dir, options):

    formats = {"m3u": M3u, "xspf": Xspf}

    # Check paths
    if not os.path.exists(pl_path):
        print "Error: playlist doesn't exist at %s. Exiting." % pl_path
        exit()

    if options.format == "auto":
        options.format = detect_format(pl_path)

        if options.format is None:
            print "Error: Couldn't autodetect format for playlist."
            exit()

    if options.format not in formats.keys():
        print "Error: Unkown '{0}' playlist format." .format(options.format)
        exit()

    if options.nocreate and not os.path.exists(remote_dir):
        print "Error: {0} doesn't exists.".format(remote_dir)
        exit()

    if not options.nocreate and not os.path.exists(remote_dir):
        try:
            os.mkdir(remote_dir)
        except OSError:
            print "Error: {0} doesn't exists and couldn't be created."\
                .format(remote_dir)
            exit()

    if not os.path.isdir(remote_dir):
        print "Error: {0} doesn't exists or is not a directory."\
                .format(remote_dir)
        exit()

    # Create playlist and sync directory
    playlist = formats[options.format](pl_path)
    files = [os.path.realpath(f[1]) for f in playlist]

    sync_dirs(files, remote_dir, options)


if __name__ == "__main__":

    # Read options
    parser = OptionParser()
    parser.add_option("-d", "--delete", dest="delete",
                      action="store_true", default=False,
                      help="Delete files which are not in the playlist.")

    parser.add_option("-f", "--force", dest="force",
                      action="store_true", default=False,
                      help="Force copy. Doesn't skip already existing files.")

    parser.add_option("-l", "--link", dest="link",
                      action="store_true", default=False,
                      help="Hard linking instead of copying files.")

    parser.add_option("-c", "--nocreate", dest="nocreate",
                      action="store_true", default=False,
                      help="Doesn't create remote directory if doesn't exists")

    parser.add_option("-s", "--shuffle", dest="shuffle",
                      action="store_true", default=False,
                      help="Process files in a random order. Useful with"
                      "--numbered.")

    parser.add_option("-n", "--numbered", dest="numbered",
                      action="store_true", default=False,
                      help="Rename files using positional indicator i_name")

    parser.add_option("-m", "--mix", dest="mix",
                      action="store_true", default=False,
                      help="Like --shuffle --numbered")

    parser.add_option("-t", "--format", dest="format",
                      action="store", default="auto",
                      help="Select format (m3u|xspf). Autodetect by default.")

    parser.set_usage("Usage: [options] playlist directory")

    (options, args) = parser.parse_args()

    # Check arguments
    errors = (("Error: Missing playlist and directory paths."),
               ("Error: Missing directory paths."),
               ("Error: Too many arguments."))

    if len(args) != 2:
        print errors[len(args) if len(args) < 3 else 2]
        print parser.print_help()
        exit()

    if options.mix:
        options.numbered = True
        options.shuffle = True

    main(args[0], args[1], options)
