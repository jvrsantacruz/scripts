# Backup

One full snapshot per backup, only changes are stored, the rest is hard-linked.

## How it works?

### The perfect backup

The perfect backup plan would save absolutely everything each time. One complete snapshot per
backup. __Sadly, this is unpractical__. it would harvest your disk and run out of space very soon.

### The almost-perfect backup

So we just have grown smarter and found a way to do it without making your disk explode. The
scripts copies everything at the first backup, and next time, it will only store the changes. I
know, just the changes aren't a full image! To make it appear as a full backup, old unchanged files
are reused and hard-linked, making them
appear in the new backup as if they were copied as well. Without taking twice the space. :)
This way each backup directory looks like a full snapshot of the data at the point.

Eg: Directories `day1` and `day2` are both apparently full backups. If you list them, all your
files are there. All the files, *as they were at the time*. But just the ones with different
*inode* numbers are really taking place in disk, the others, are linked.

	day1                        day2
	|                            |
	|- 1550 unchanged.txt  --->  |- 1550 unchanged.txt
	`- 1327 changed.txt          `- 8702 changed.txt

	             data in disk:
	               - 1550 unchanged.txt
	               - 1327 changed.txt
	               - 8702 changed.txt

## How to use it?

The script needs to know where to get the data, and where to save it: 

1. Directories/Files to save (*origins*)
2. Directory to store the data (*destination*)
3. Action (backup, rotate, test)

`python backup.py --origin /home/fulano --origin /home/mengano --dest /media/usb-disk backup`

As it's `rsync` based, it is not necessary for origins to be local directories. You can
mix and chose to *pull* the data from other machine to a local safer place.

You can provide all the options on the command-line, but a more reasonable way to use the script is
to write a backup plan. A plan is a named backup task. It defines origins, destination and options
in the friendly YAML format, and this way, only the plan file has to be passed to the program.

`python backup.py --plan backup-home.yaml backup`

See more about this in the *Plan* section.

## Actions

The script accept the following *verbs*, which indicate what it should do:

- **test**: Tests the backup scheme. No data it's copied, no directories are created.
- **rotate**: Create weekly directories in *dest* directory and move old backups to them.
- **backup**: Performs a regular backup.

Usually rotate takes an option, which indicates how many backups it should be until moving them
to weekly directories.
Tests relies on the rsync option `--dry-run` so connection, logging and net data transfer will be also tested.

### Paths

- Origin paths can be relative to the config file, if its present. They will be relative to the script otherwise.
- Paths will be redirected straight to rsync so it can be anything that rsync understands.
  Have in account that if rsync prompts asking password for ssh, it will stop the script when
  running from cron.


## The Plan file

The plan file supports each single command-line option in its *long* form.  For single options,
just write `name: value`, for multiple options, the ones that can have more than one value, you set
a *YAML* list.

For example, to set two paths as origins, you would write a YAML list in the config file:

	origins:
	- /path/value
	- /path/other

All available options for a plan can be consulted by calling the script using the
`--list-opts` flag. It will show each option, showing if its a list and its default value.

### Plan examples

The following plan can backup some user local directories. Origins are local and so destination. We
also set some options in the plan, we exclude certain patterns in the paths being saved.

	# Where to store the backups
	dest: /media/external/bk

	# Directories to be backed up
	origins:
	- /home/jvr/Dropbox
	- /home/jvr/.config

	exclude:
	- ".dropbox"
	- "*.cache"

This other plan it's what I use to backup my smartphone on a local network through ssh.
The plan also sets some options `rotate_max`, `logfile` and the `verbose` level.

	dest: /home/jvr/backup/nexus

	origins:
	- /sdcard

	# ssh options for all origins
	origin_user: root
	origin_host: 192.168.1.11

	logfile: /home/jvr/backup/nexus.log

	# Change permissions on the copy and follow symlinks
	rsync_args:
	- "--chmod=u+rwx"
	- "-L"

	excludes:
	- .cache/*
	- .thumbnails
	- .image-cache

We're using here the rsync's own protocol. This is a real set-up example to backup a *Windows 7*
box running a [cwRsync][] server. This is cake when one's have to backup lots of different hosts
and avoid re-configure each single machine when a change in the backup-policy its made.

The `rsync_args` option should also draw your attention, it takes options for rsync that are sent
straight to the command-line order; This is very important when backing up certain file-systems or
when you want to override some option set by default by the script with a `-no-OPT` rsync option.

## Teorical drawbacks

There's almost no inconvenience in this system except for the directory space bloat, which can be
significant when performing really small backups (with delta changes of bytes) and dense directory
trees. Big changing files should also be avoided. Main inconveniences found in this system:

1. You cannot hard-link directory entries, so they'll have to be re-created each time a backup is
made. This means some extra megabytes per backup taken for directories, even if there is no changes
in data between copies.

2. If you have to replicate a whole image of your disk by hard-linking files one-by-one, it can
take some time before each one of them has been consulted and linked when you have a very high
number of files.

3. Changing big files are evil. A big file constantly changing means a big file being copied one
time and another, and can represent a big space problem.

## Options

The complete list of arguments:

	Usage: backup.py Usage: [options] [--plan plan] backup|rotate|test

	Options:
	-h, --help            show this help message and exit
	-p PLAN, --plan=PLAN  Backup plan definition.
	-o ORIGINS, --origin=ORIGINS
							Add location to backup. Can be called multiple times
	-d DEST, --dest=DEST  Where to store the backup.
	-m ROTATE_MAX, --max=ROTATE_MAX
							Max number of backups stored. Default 10.
	--host=ORIGIN_HOST    Host for origins if needed.
	-g ORIGIN_MODULE, --module=ORIGIN_MODULE
							Module for origins if needed.
	-u ORIGIN_USER, --user=ORIGIN_USER
							User for ssh origins if needed.
	-e EXCLUDE, --exclude=EXCLUDE
							Exclude patterns. Can be called multiple times
	-s MAX_SIZE, --max-size=MAX_SIZE
							Exclude big files. Default 500M.
	-a RSYNC_ARGS, --rsync-args=RSYNC_ARGS
							Extra args for rsync. Can be called multiple times
	-l LOGFILE, --logfile=LOGFILE
							Path to logfile to store log. Will log to stdout if
							unset.
	-j PRE_HOOK, --pre-hook=PRE_HOOK
							Order to be called before backup.
	--pre-hook-args       Pass to the pre_hook order the following arguments:
							DEST_DIR, LOGFILE, ORIGINS+
	-k POST_HOOK, --post-hook=POST_HOOK
							Order to be called after the backup.
	--post-hook-args      Pass to the post_hook order the following arguments:
							DEST_DIR, LOGFILE, ORIGINS+
	--list-opts           Lists recognized plan options and type.
	-v, --verbose         Verbosity. Default silent. -v (info)  -vv (debug)

## Dependences:

- python2.6
- python-yaml
- rsync 2.6+

[cwRsync]: http://www.itefix.no/i2/cwrsync
