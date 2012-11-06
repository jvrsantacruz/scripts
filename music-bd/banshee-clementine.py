#!/usr/bin/env python
#-*- coding: utf-8 -*-
"""
Syncs playcounts and ratings between banshee and clementine databases.

Javier Santacruz 12/12/2011
"""

import sys
import shutil
import logging
import sqlite3
import tempfile
from abc import ABCMeta
from optparse import OptionParser

_LOGGING_FMT_ = '%(asctime)s %(levelname)-8s %(message)s'


def error(msg, is_exit=True):
    logging.error(str(msg))
    if is_exit:
        sys.exit()


class Dbfile(object):
    """Dbfile Banshee/Clementine operations"""

    _QUERIES = {
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

            'update': {
                'overwrite': """
                              UPDATE CoreTracks
                              SET Rating = :rating,
                                  PlayCount = :play,
                                  SkipCount = :skip
                              WHERE CoreTracks.TrackID = (
                                SELECT CoreTracks.TrackID
                                FROM CoreTracks
                                INNER JOIN CoreArtists
                                  ON CoreTracks.ArtistID = CoreArtists.ArtistID
                                INNER JOIN CoreAlbums
                                  ON CoreTracks.AlbumID = CoreAlbums.AlbumID
                                WHERE  CoreTracks.Title = :title
                                  AND CoreArtists.Name = :artist
                                  AND CoreAlbums.Title = :album
                                LIMIT 1);
                              """,

                'noverwrite': """
                                UPDATE CoreTracks
                                SET Rating = :rating,
                                    PlayCount = PlayCount + :play,
                                    SkipCount = SkipCount + :skip
                                WHERE CoreTracks.TrackID = (
                                  SELECT CoreTracks.TrackID
                                  FROM CoreTracks
                                  INNER JOIN CoreArtists
                                  ON CoreTracks.ArtistID = CoreArtists.ArtistID
                                  INNER JOIN CoreAlbums
                                  ON CoreTracks.AlbumID = CoreAlbums.AlbumID
                                  WHERE  CoreTracks.Title = :title
                                    AND CoreArtists.Name = :artist
                                    AND CoreAlbums.Title = :album
                                  LIMIT 1);
                                """
            }
    },

        'clementine': {

            'extract': """
            SELECT artist,album,title,rating,playcount,skipcount
            FROM songs
            WHERE rating > -1
            OR playcount > 0
            OR skipcount > 0
            ORDER BY artist,album,title;
            """,

            'update': {
                'overwrite': """
                              UPDATE songs
                              SET rating = :rating,
                              playcount = :play,
                              skipcount = :skip
                              WHERE artist = :artist
                              AND album = :album
                              AND title = :title;
                              """
                             ,

                'noverwrite':  """
                               UPDATE songs
                               SET rating = :rating,
                               playcount = playcount + :play,
                               skipcount = skipcount + :skip
                               WHERE artist = :artist
                               AND album = :album
                               AND title = :title;
                               """
            }
        }
    }

    # Known tables for each format
    _TABLES = { 'banshee': ['CoreTracks', 'CoreAlbums', 'CoreArtists'],
               'clementine': ['songs', 'playlists', 'playlist_items']
              }

    def __init__(self, dbpath):
        self.dbpath = dbpath
        self.bkpath = self.backup_db()

        self.conn = self.open_db(self.bkpath)
        self.format = self.detect_format()

    @staticmethod
    def open_db(dbpath):
        "Opens and returns a sqlite connection"
        try:
            return sqlite3.connect(dbpath)
        except sqlite3.DatabaseError, err:
            error("Couldn't connect to database in {0}: {1}"
                  .format(dbpath, err))

    def row(self, rawrow):
        "Returns a RowOperations object from a given sqlite row"
        # Get operations object
        if self.format is 'banshee':
            return BansheeRow(rawrow)
        elif self.format is 'clementine':
            return ClementineRow(rawrow)
        else:
            error("Unkown format for dbfile: {0}".format(self.dbpath))

    def backup_db(self):
        """Backs the destination database into a temporary file.
        Returns the path for the copy or None in case of failure
        """
        with tempfile.NamedTemporaryFile(delete=False) as bkfile:
            with open(self.dbpath, 'r') as origfile:
                shutil.copyfileobj(origfile, bkfile)
                logging.info("Backed up {0} to {1}".format(self.dbpath, bkfile.name))
                return bkfile.name

        error("Couldn't backup {0}".format(self.dbpath))

    def detect_format(self):
        """Returns the format for the database which conn is connected:
            banshee - Banshee format
            clementine - Clementine format
            None - Unknown
        """
        cursor = self.conn.cursor()
        for db, tests in self._TABLES.iteritems():
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

    def copy_data(self, from_db, overwrite=False):
        """Copies and sets values from 'from_db' to database backup
        Default behaviour is to add playcounts and skipcounts
        use overwrite to avoid this.
        """
        # Get cursors for backup files
        tocur, fromcur = self.conn.cursor(), self.conn.cursor()
        overw = 'overwrite' if overwrite else 'noverwrite'

        # Query all tracks from 'from_db'
        logging.info("Retrieving data from {0}".format(from_db.dbpath))
        try:
            fromcur.execute(self._QUERIES[from_db.format]['extract'])
        except sqlite3.DatabaseError, err:
            error("Error detected while extracting from {0}: {1}"\
                .format(from_db.dbpath, str(err)))

        # Update database
        logging.info("Updating {0}'s ratings and counters".format(self.dbpath))
        counter = 0
        for row in fromcur:
            row = from_db.row(row)

            # Check whether the row should be updated
            if not row.check():
                logging.debug("Ignoring row: {0}".format(row.row))
                continue

            # Transform numeric schemes from from_db to this db format
            row.transform(self.format)

            logging.debug("Changing row: {0}".format(row.row))

            try:
                tocur.execute(self._QUERIES[self.format]['update'][overw],
                              { "artist":  row['artist'],
                                "album":   row['album'],
                                "title":   row['title'],
                                "rating":  float(row['rating']),
                                "play":    int(row['play']),
                                "skip":    int(row['skip']) })

            except sqlite3.DatabaseError, err:
                error("Error detected while updating db: {0}".format(err))
            counter += 1

        logging.info("{0} tracks successfully updated".format(counter))

    def close(self):
        "Closes internal connection"
        self.conn.close()

    def commit(self):
        "Commit changes and overwrite original db"
        # commit changes
        self.conn.commit()
        try:
            shutil.move(self.bkpath, self.dbpath)
        except shutil.Error:
            error("Couldn't overwrite {1} with {0}"
                  .format(self.dbpath, self.bkpath))
        else:
            logging.info("Updated {0}".format(self.dbpath))


class RowOperations(object):
    "Common row operatons. Abstract class, do not instantiate"

    __metaclass__ = ABCMeta

    _fields = ['artist', 'album', 'title', 'rating', 'play', 'skip']

    def __init__(self, row):
        self.row = list(row)

    def check(self):
        "Returns True if it should be updated"
        if opts.only_rated:
            return self.is_rated()

        return self.is_rated() or self.is_played() or self.is_skipped()

    def is_played(self):
        "Returns if the row has playcounts"
        # row fields: [artist album title rating playcount skipcount]
        return self.row[4] > 0

    def is_skipped(self):
        "Returns if the row has skipcounts"
        # row fields: [artist album title rating playcount skipcount]
        return self.row[5] > 0

    def _find(self, name):
        for i, field in enumerate(self._fields):
            if field == name:
                return i

    def __getitem__(self, key):
        if isinstance(key, str):
            key = self._find(key)
            if key is None:
                raise IndexError("{0} is not a field of row".format(key))

        return self.row[key]

    def __setitem__(self, key, val):
        if isinstance(key, str):
            key = self._find(key)
            if key is None:
                raise IndexError("{0} is not a field of row".format(key))

        self.row[key] = val


class BansheeRow(RowOperations):
    "Banshee row operations"

    def is_rated(self):
        "Returns if the row has been rated"
        # row fields: [artist album title rating playcount skipcount]
        return self.row[3] == 0

    def transform(self, to_format):
        """Transforms and returns the row to to_format
        Move ratings from [-1-5] to [0-1] for clementine
        """
        # row fields: [artist album title rating playcount skipcount]
        if to_format == 'clementine':
            if self.row[3] == -1:
                self.row[3] = 0
            self.row[3] *= 0.2

        return self.row


class ClementineRow(RowOperations):
    "Clementine row operations"

    def is_rated(self):
        "Returns if the row has been rated"
        # row fields: [artist album title rating playcount skipcount]
        return self.row[3] == -1

    def transform(self, to_format):
        """Transforms and returns the row to to_format
        Move ratings from [0-1] to [-1-5] for banshee
        """
        # row fields: [artist album title rating playcount skipcount]
        if to_format == 'banshee':
            self.row[3] *= 5
            if self.row[3] == 0:
                self.row[3] = -1

        return self.row


def main(opts, args):

    from_db, to_db = Dbfile(opts.dbfrom), Dbfile(opts.dbto)

    to_db.copy_data(from_db, opts.overwrite)
    to_db.commit()
    to_db.close()
    from_db.close()

if __name__ == "__main__":
    parser = OptionParser()

    parser.add_option("-f", "--from", dest="dbfrom",
                      action="store", default="",
                      help="Source database path")

    parser.add_option("-r", "--only-rated", dest="only_rated",
                      action="store_true", default=False,
                      help="Ignore unrated songs")

    parser.add_option("-o", "--overwrite", dest="overwrite",
                      action="store_true", default=False,
                      help="Overwrites playcounts instead of adding them")

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
