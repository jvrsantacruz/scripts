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
        title = self.list[self.index].title.text.encode('utf-8')
        path = self.list[self.index].location.text.encode('utf-8')[7:]

        self.index += 1  # next track

        return title, path


class M3u(PIterable):
    "Iterate over a M3U playlist file."

    ns = "#EXTM3U"

    def __init__(self, path):
        super(M3u, self).__init__(path)
        self.base_path = os.path.dirname(self.path)
        self.file = open(self.path, "r")

    def next(self):
        """Returns title, absolute_path for every item on the playlist.

        M3u objects have the following structure:

        #EXTM3U
        #EXTINF:342,Author - Song Title
        ../Music/song.mp3
        """

        # Find a #EXTINF line and a path line
        line, line_prev = '#', ''
        while line.startswith('#'):
            line_prev = line
            line = self.file.readline()
            if not line:
                raise StopIteration

        title = line_prev.split(',', 1)[1]  # get title
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


_FORMATS_ = {"m3u": M3u, "xspf": Xspf}


def get_playlist(path, pformat=None):
    """Returns a Playlist object of the given format.
    "if pformat is not specified or None, format will be auto detected
    """
    if pformat is None:
        pformat = detect_format(path)

    if pformat is None:
        print "Error: Couldn't autodetect format for playlist."
        exit()

    if pformat not in _FORMATS_.keys():
        print "Error: Unkown '{0}' playlist format." .format(options.format)
        exit()

    # Create playlist and sync directory
    return _FORMATS_[pformat](path)


def prefix_name(number, name, total):
    """Returns name prefixed with number. Filled with zeros to fit total
    >>> prefix_name(15, 'filename', 3)
    '015_filename'
    >>> prefix_name(15, 'filename', 1)
    '15_filename'
    """
    return "{0}_{1}".format(str(number).zfill(len(str(total))), name)


def get_expected_names(local_files):
    "Returns the filenames expected to be on remote"
    if not options.numbered:
        return local_files

    return [prefix_name(i + 1, f, len(local_files))
            for i, f in enumerate(local_files)]


def get_copy_names(local_files, expected_names, remote_names):
    "Returns the files to be copied"
    if options.force:
        return local_files  # copy all of them

    return [f for i, f in enumerate(local_files)
            if expected_names[i] not in remote_names]


def delete_files(expected_names, remote_dir):
    """Deletes files in remote which aren't expected to be there
    Returns the name of files effectively deleted
    """
    delete_list = [os.path.join(remote_dir, f)
                   for f in os.listdir(remote_dir)
                   if f not in expected_names]

    print "Removing {0} files from {1}".format(len(delete_list), remote_dir)

    deleted = 0
    for fpath in delete_list:
        try:
            os.remove(fpath)
        except OSError, err:
            print "Error: Couldn't remove {0} from {1}: {2}"\
                    .format(os.path.basename(fpath), remote_dir, err)
        else:
            deleted += 1
            print "Removed {0}/{1}: {2}"\
                    .format(deleted, len(delete_list), fpath)

    return deleted


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


def send_files(copy_files, expected_names, remote_dir, dolink=False):
    """Copies/Links files to remote dir as expected_name
    Links instead of copying the files if link is True
    returns the number of files copied/linked
    """
    action = "Linking" if dolink else "Copying"
    print "{0} {1} files to {2}".format(action, len(copy_files), remote_dir)
    action = "Linked" if dolink else "Copied"
    copied = 0
    for i, cfile in enumerate(copy_files):
        dest = os.path.join(remote_dir, expected_names[i])
        if os.path.exists(dest):
            print "Warning: Destination {0} already exists".format(dest)
            continue
        op_result = link(cfile, dest) if dolink else copy(cfile, dest)
        if op_result:
            copied += 1
            print "{0} {1}/{2}: {3}".format(action, copied,
                                            len(copy_files), cfile)
    return copied


def sync_dirs(local_files, remote_dir, opts):
    """Copy a set files to a directory.
    If delete is set, will remove files in remote which are not in local.
    If link is set, will perform hard link instead of copy.
    If force is set, will copy all files ignoring if they're already in remote.
    """
    if opts.cd:
        # Maximize de number of files in the CD
        # omit files until the result fit's into a CD big ones first
        weighted_files = map(lambda f: (os.path.getsize(f) * 5, f), local_files)
        weighted_files.sort(key=lambda f: f[0], reverse=True)  # biggers first
        adder = lambda x, y: x[0] if isinstance(x, tuple) else x + y[0]
        total_size = reduce(adder, weighted_files)

        cdsize = 700 * 1024 * 1024  # in bytes
        while total_size > cdsize:
            size,f = weighted_files.pop()
            print "Ommiting {0} to fit CD size".format(f)
            local_files.remove(f)
            total_size -= size

    # Obtain file names in order to compare file subsets
    if opts.shuffle:
        random.shuffle(local_files)

    local_names = [os.path.basename(f) for f in local_files]  # local names
    expected_names = get_expected_names(local_names)  # what sould be in remote
    remote_names = os.listdir(remote_dir)             # what is in remote

    # Remove undesired files
    deleted = 0
    if opts.delete:
        deleted = delete_files(expected_names, remote_dir)

    # Paths to be copied to remote
    copy_files = get_copy_names(local_files, expected_names, remote_names)

    # Warn about already present files which are being skipped
    if not opts.force:
        for f in set(remote_names).intersection(set(expected_names)):
            print "Skipping {0} which is already in {1}"\
                    .format(os.path.basename(f), remote_dir)

    # Copy/Link files to remote directory
    copied = send_files(copy_files, expected_names, remote_dir, opts.link)
    action = "Linking" if opts.link else "Copying"

    print "{0} complete: {1} files copied, {2} files removed"\
            .format(action, copied, deleted)


def main():

    pl_path = args[0]
    remote_dir = args[1]

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

    playlist = get_playlist(pl_path, options.format)
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

    parser.add_option("-7", "--cd", dest="cd",
                      action="store_true", default=False,
                      help="Limits the list size to 700MiB")

    parser.add_option("-t", "--format", dest="format",
                      action="store", default=None,
                      help="Select format (m3u|xspf). Autodetects by default.")

    parser.set_usage("Usage: [options] playlist directory")

    (options, args) = parser.parse_args()

    # Check arguments
    errors = (("Error: Missing playlist and directory paths."),
               ("Error: Missing directory paths."),
               ("Error: Too many arguments."))

    if len(args) != 2:
        print errors[len(args) if len(args) < 3 else 2]
        print parser.print_help()
        exit(1)

    if options.mix:
        options.numbered = True
        options.shuffle = True

    if not os.path.isfile(args[0]):
        print "Error: playlist doesn't exist or isn't a file: {0}. Exiting."\
                .format(args[0])
        exit(1)

    main()
