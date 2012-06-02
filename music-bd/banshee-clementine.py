#!/usr/bin/env python
#-*- coding: utf-8 -*-
"""
Syncs playcounts and ratings between banshee and clementine databases.

Javier Santacruz 12/12/2011
"""

import sys
import time
import shutil
import logging
import sqlite3
from optparse import OptionParser

_LOGGING_FMT_ = '%(asctime)s %(levelname)-8s %(message)s'

_QUERIES_ = {
    'banshee': {

        'extract': """
        SELECT CoreArtists.Name, CoreAlbums.Title, CoreTracks.Title,
               CoreTracks.Rating, CoreTracks.PlayCount, CoreTracks.SkipCount
        FROM CoreTracks
        INNER JOIN CoreArtists ON CoreTracks.ArtistID = CoreArtists.ArtistID
        INNER JOIN CoreAlbums ON CoreTracks.AlbumID = CoreAlbums.AlbumID

        WHERE CoreTracks.Rating > 0
        OR CoreTracks.PlayCount > 0
        OR CoreTracks.SkipCount > 0
        ORDER BY CoreArtists.Name,CoreAlbums.Title,CoreTracks.Title;
        """,

        'update': """
        UPDATE CoreTracks
        SET Rating = :rating, PlayCount = :play, SkipCount = :skip
        WHERE CoreTracks.TrackID = (
         SELECT CoreTracks.TrackID
         FROM CoreTracks
          INNER JOIN CoreArtists ON CoreTracks.ArtistID = CoreArtists.ArtistID
          INNER JOIN CoreAlbums ON CoreTracks.AlbumID = CoreAlbums.AlbumID
          WHERE  CoreTracks.Title = :title
           AND CoreArtists.Name = :artist
           AND CoreAlbums.Title = :album
           LIMIT 1);
        """},

    'clementine': {

        'extract': """
        SELECT artist,album,title,rating,playcount,skipcount
        FROM songs
        WHERE rating > -1
        OR playcount > 0
        OR skipcount > 0
        ORDER BY artist,album,title;
        """,

        'update': """
        UPDATE songs
        SET rating = :rating,
        playcount = :play,
        skipcount = :skip
        WHERE artist = :artist
        AND album = :album
        AND title = :title;
        """}
}


def error(msg, is_exit=True):
    logging.error(str(msg))
    if is_exit:
        sys.exit()


def backup_db(dbpath):
    """
    Backs up a given database
    Returns the path for the copy
    """
    backup = "{0}-{1}.bk".format(dbpath, str(time.time()))
    try:
        shutil.copy(dbpath, backup)
    except shutil.Error:
        error("Couldn't copy {0} to {1}".format(dbpath, backup))
    else:
        logging.info("Backed up {0} to {1}".format(dbpath, backup))

    return backup


def transform_row(row, from_format, to_format):
    """
    Transforms a row into others database format
    """
    if from_format == to_format:
        return row

    row = list(row)
    if from_format == 'banshee':
        row[3] *= 0.2  # clementine uses (0-10)/10

    elif from_format == 'clementine':
        row[3] *= 5  # banshees uses 0-5

    return row


def check_row(row, dbformat):
    """
    Checks whether a row should be used for update or not
    """
    # [artist album title rating playcount skipcount]
    if dbformat == 'banshee':
        return row[3] > 0 or row[4] > 0 or row[5] > 0
    elif dbformat == 'clementine':
        return row[3] != -1 or row[4] > 0 or row[5] > 0


def detect_format(conn):
    """
    Returns the format for the database which conn is connected:
        banshee - Banshee format
        clementine - Clementine format
        None - Unknown
    """
    # Known tables for each format
    dbs = {
        'banshee': ['CoreTracks', 'CoreAlbums', 'CoreArtists'],
        'clementine': ['songs', 'playlists', 'playlist_items']
    }

    cursor = conn.cursor()
    for db, tests in dbs.iteritems():
        dbformat = db
        try:
            for table in tests:
                cursor.execute("SELECT * FROM {0} LIMIT 1".format(table))
        except sqlite3.DatabaseError:
            logging.debug("Failed query using table {1}".format(table))
            dbformat = None
        else:
            # If all tests for a given format passed, that's it
            return dbformat


def main(opts, args):

    logging.info("Backing up databases...")
    frombackup = backup_db(opts.dbfrom)
    tobackup = backup_db(opts.dbto)
    #shutil.copy(opts.dbto, "{0}-{1}.bk".format(opts.dbto, str(time.time())))

    # We'll use the copied db to write to and read from
    # in order to avoid concurrence pitfalls
    logging.info("Conecting to databases...")
    try:
        fromconn = sqlite3.connect(frombackup)
    except sqlite3.DatabaseError:
        error("Couldn't connect to database: {0}".format(frombackup))

    try:
        toconn = sqlite3.connect(tobackup)
    except sqlite3.DatabaseError:
        error("Couldn't connect to database: {0}".format(tobackup))

    logging.info("Checking formats...")
    opts.dbfrom_format = detect_format(fromconn)
    if opts.dbfrom_format is None:
        error("Unknown format for {0}".format(opts.dbfrom))

    opts.dbto_format = detect_format(toconn)
    if opts.dbto_format is None:
        error("Unknown format for {0}".format(opts.dbto))

    logging.info("Extracting from {0} ({1}) to {2} ({3})"\
            .format(os.path.basename(frombackup), opts.dbfrom_format,
                    os.path.basename(tobackup), opts.dbto_format))

    # Get cursors
    fromcur, tocur = fromconn.cursor(), toconn.cursor()

    # Get the data
    logging.info("Retrieving data from {0}".format(frombackup))
    try:
        fromcur.execute(_QUERIES_[opts.dbfrom_format]['extract'])
    except sqlite3.DatabaseError, err:
        error("Error detected while extracting from {0}: {1}"\
              .format(frombackup, str(err)))

    # Update database
    logging.info("Updating {0} ratings and counters".format(tobackup))
    for row in fromcur:
        # Check whether the row should be updated
        if not check_row(row, opts.dbfrom_format):
            continue

        # Transform numeric schemes
        row = transform_row(row, opts.dbfrom_format, opts.dbto_format)

        try:
            # artist album title rating
            tocur.execute(_QUERIES_[opts.dbto_format]['update'],
                          {"artist": row[0], "album": row[1], "title": row[2],
                           "rating": float(row[3]), "play": int(row[4]),
                           "skip": int(row[5])})
        except sqlite3.DatabaseError, err:
            error("Error detected while updating db: {0}".format(err))

    # commit changes
    toconn.commit()

    logging.info("Substituting original database {0} with the copy {1}"\
            .format(os.path.basename(opts.dbto), os.path.basename(tobackup)))
    try:
        shutil.move(tobackup, opts.dbto)
    except shutil.Error, err:
        error("Error detected while setting {0} from the new database {1}"\
            .format(os.path.basename(opts.dbto), os.path.basename(tobackup)))

    # Close connections
    fromconn.close()
    toconn.close()

if __name__ == "__main__":
    parser = OptionParser()

    parser.add_option("-f", "--from", dest="dbfrom",
                      action="store", default="",
                      help="Source database path")

    parser.add_option("-t", "--to", dest="dbto",
                      action="store", default="",
                      help="Destination database path")

    parser.add_option("-v", "--verbose", dest="verbose",
                      action="count", default=0,
                      help="Verbosity. Default silent. -v (info) -vv (debug)")

    parser.set_usage("Exports ratings/playcounts from one clementine/banshee "
                     "db to another\n\tUsage: [options] [dbfrom, [dbto]]\n")

    (opts, args) = parser.parse_args()

    if len(args) > 1:
        opts.dbfrom = args.pop(0)
        opts.dbto = args.pop(0)

    logging_levels = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}
    level = logging_levels[opts.verbose if opts.verbose < 3 else 2]
    logging.basicConfig(level=level, format=_LOGGING_FMT_)

    if not opts.dbfrom or not opts.dbto:
        parser.print_help()
        error("Should provide Source and Destination databases")

    main(opts, args)
