#!/usr/bin/env python
#-*- coding: utf-8 -*-
"""
Hashes audio files ignoring metadata

id3v1 is 128 bytes at the end of the file starting with 'TAG'
id3v1 extended is 227 bytes before regular id3v1 tag starting with 'TAG+'
total size: 128 + (227 if extended)

id3v2 has a 10 bytes header at the begining of the file.
      byte 5 holds flags. 6th bit indicates extended tag
      bytes 6-10 are the tag size (not counting header)
id3v2 extended has a 10 bytes header after the regular id3v2
      bytes 1-4 are the tag size (not counting header nor padding)
      bytes 4-6 holds some flags. Leftmost bit indicates CRC presence
      bytes 6-10 are the tag padding size (extra blank size within tag)
total size: 10 + tagsize + (10 + etagsize + padding if extended)

Based on id3v1 wikipedia docs: http://en.wikipedia.org/wiki/ID3
Based on id3v2 docs: http://www.id3.org/id3v2.3.0

Javier Santacruz 2012-06-03
"""

import os
import sys
import struct
import hashlib
import logging
from optparse import OptionParser

_LOGGING_FMT_ = '%(asctime)s %(levelname)-8s %(message)s'


def error(msg, is_exit=True):
    logging.error(msg)
    if is_exit:
        sys.exit()


def id3v1exists(ofile):
    "Returns True if the file is id3v1 tagged"
    ofile.seek(-128, 2)
    return ofile.read(3) == 'TAG'


def id3v1isextended(ofile):
    "Returns True if the file is id3v1 with extended tag"
    ofile.seek(-(227 + 128), 2)  # 227 before regular tag
    return ofile.read(4) == 'TAG+'


def id3v1extsize(ofile):
    "Returns the size of the extended tag"
    return 227


def id3v1size(ofile):
    "Returns the size in bytes of the id3v1 tag"
    size = 128
    if id3v1isextended(ofile):
        size += id3v1extsize(ofile)

    return size


def id3v2exists(ofile):
    "Returns True if the file is id3v2 tagged"
    ofile.seek(0)
    return ofile.read(3) == 'ID3'


def id3v2isextended(ofile):
    "Returns True if the file has id3v2 extended header"
    ofile.seek(5)
    flags, = struct.unpack('>b', ofile.read(1))
    return bool(flags & 0x40)  # xAx0 0000 get A from byte


def id3v2extsize(ofile, tagsize):
    "Returns the size in bytes of the id3v2 extended tag"
    ofile.seek(tagsize)
    size = struct.unpack('>i', ofile.read(4))
    flags, = struct.unpack('>bb', ofile.read(2))
    crc = 4 if flags & 8 else 0  # flags are A000 get A
    padding = struct.upnack('>i', ofile.read(4))
    return size + crc + padding + 10


def id3v2size(ofile):
    "Returns the size in bytes of the id3v2 tag"
    ofile.seek(6)
    size, = struct.unpack('>i', ofile.read(4))  # id3v2 size big endian 4 bytes
    size += 10  # header itself

    if id3v2isextended(ofile):
        size += id3v2extsize(ofile, size)

    return size


def hashfile(ofile, start, end, alg='sha1'):
    "Hashes a open file data starting from byte 'start' to the byte 'end'"
    hasher = hashlib.new(alg)
    ofile.seek(start)

    size = end - start                 # total size in bytes to hash
    blocksize = 524288                 # block size 512 KiB
    nblocks = size // blocksize        # n full blocks
    firstblocksize = size % blocksize  # spare data, not enough for a block

    logging.debug("Start: {0} End: {1} Size: {2}".format(start, end, size))

    block = ''
    try:
        if firstblocksize > 0:
            block = ofile.read(firstblocksize)
            for i in xrange(nblocks):
                hasher.update(block)
                block = ofile.read(blocksize)
    finally:
        ofile.close()

    return hasher.hexdigest()


def startbyte(ofile):
    "Returns the byte where the music starts"
    if id3v2exists(ofile):
        return id3v2size(ofile)
    else:
        return 0


def endbyte(ofile):
    "Returns the last byte of music"
    if id3v1exists(ofile):
        return id3v1size(ofile)
    else:
        ofile.seek(-1, 2)
        return ofile.tell()


def musiclimits(ofile):
    "Returns the start, end for music in a file"
    return (startbyte(ofile), endbyte(ofile),)


def mp3hash(path, alg='sha1'):
    "Returns the hash for a certain audio file ignoring tags"
    with open(path, 'rb') as ofile:
        start, end = musiclimits(ofile)
        return hashfile(ofile, start, end, opts.algorithm)


def list_algorithms():
    for alg in hashlib.algorithms:
        print alg
    sys.exit(0)


def main():
    "Main program"

    if opts.list_algorithms:
        list_algorithms()

    for arg in args:
        arg = os.path.realpath(arg)
        if not os.path.isfile(arg):
            logging.error("Couldn't open {0}. File doesn't exist or isn't a"
                          " regular file".format(arg))
            continue

        with open(arg, 'rb') as ofile:
            start, end = musiclimits(ofile)
            print hashfile(ofile, start, end, opts.algorithm), \
                    os.path.basename(arg) if not opts.hash else ''


if __name__ == "__main__":
    parser = OptionParser()

    parser.add_option("-a", "--algorithm", dest="algorithm", action="store",
                      default='sha1', help="Hash algorithm to use. "
                      "Default sha1.  See --list-algorithms")

    parser.add_option("-l", "--list-algorithms", dest="list_algorithms",
                      action="store_true", default=False,
                      help="List available algorithms")

    parser.add_option("-q", "--hash", dest="hash", action="store_true",
                      default=False, help="Print only hash information, no "
                      "filename")

    parser.add_option("-o", "--output", dest="output", action="store",
                      default=False, help="Redirect output to a file")

    parser.add_option("-v", "--verbose", dest="verbose", action="count",
                      default=0, help="")

    parser.set_usage("Usage: [options] FILE [FILE ..]")

    (opts, args) = parser.parse_args()

    # Configure logging
    logging_levels = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}
    level = logging_levels[opts.verbose if opts.verbose < 3 else 2]
    logging.basicConfig(level=level, format=_LOGGING_FMT_)

    if opts.output:
        try:
            sys.stdout = open(opts.output, 'w')
        except IOError, err:
            error("Couldn't open {0}: {1}".format(sys.stdout, err))

    main()
