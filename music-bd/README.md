# Banshee-Clementine database sync

Updates `playcount`, `skipcount` and `rating` from a `Banshee`/`Clementine` database to another.
Use it like this:

	$ python banshee-clementine -v ~/.config/Banshee/banshee.db ~/.config/Clementine/clementine.db
	2012-06-02 22:15:10,480 INFO     Backed up ~/.config/Clementine/clementine.db to
											   ~/.config/Clementine/clementine.db-1338668110.41.bk
	2012-06-02 22:15:10,548 INFO     Backed up ~/.config/Clementine/clementine.db to
	                                           ~/.config/Clementine/clementine.db-1338668110.48.bk
	2012-06-02 22:15:10,551 INFO     Retrieving data from ~/.config/Clementine/clementine.db
	2012-06-02 22:15:10,578 INFO     Updating ~/.config/Clementine/clementine.db's ratings and counters
	2012-06-02 22:15:10,912 INFO     2741 tracks successfully updated
	2012-06-02 22:15:11,267 INFO     Updated ~/.config/Clementine/clementine.db


It will set all ratings in the `Banshee` database tracks to the ones in `Clementine`, and update
their playcounts and skipcounts adding them to the existent ones. 
Reload the database (`Clementine` in this case) and you shall see the same ratings and the updated
playcounts as they were in the Banshee database.

You could also use it `Banshee` to `Banshee` or `Clementine` to `Clementine`, it doesn't matter.

Default behaviour is to add old counts to the new ones, but you can avoid this by using the
`--overwrite` flag, which will make overwrite counts in the destination.database All tracks with
either rating or counts are updated. You can restrain this to update only the rated tracks by using
the `--only-rated` flag.

I wrote this scripts when moving from `Banshee` to `Clementine` music player. I hated the idea of
completely lost all ratings assigned to songs, and so playcounts, which I use to create smart
playlists and statistics. Now I also use it when I install Clementine on another computer on the
same collection. Just grab the old `Clementine` database and sync with the new empty one.

# How it works?

Both `Banshee` and `Clementine` use `sqlite` for its database, so all the script has to do its to
query them song by song (by matching title, album and artist) and grab and convert their values.

Conversion is needed due to different punctuation systems. `Clementine`'s ratings are in `[0-5]`
and uses -1 for unrated songs, while `Banshee`'s ratings are in `[0-1]` and uses 0 for unrated
songs.

# Options

	Exports ratings/playcounts from one clementine/banshee db to another
	Usage: banshee-clementine.py [options] [dbfrom, [dbto]]

	Options:
	-h, --help    	          Show this help message and exit
	-f DBFROM, --from=DBFROM  Source database path
	-t DBTO, --to=DBTO    	  Destination database path
	-r,--only-rated 		  Ignore unrated songs
	-o,--overwrite 			  Overwrites playcounts instead of adding them
	-v, --verbose             Verbosity. Default silent. -v (info) -vv (debug)

# Dependences

python-sqlite3
