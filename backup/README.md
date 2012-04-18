# Backup

One full snapshot per backup, only changes are stored, the rest is hard-linked.

## How it works?

### The perfect backup

The perfect backup plan would save absolutely everything each time it's called. One complete
snapshot each time.
This way, accessing to old versions and restoring them would be completely straightforward.
__Sadly, this is unpractical__. You would harvest your disk and run out of space very soon.

### The almost-perfect backup

So we just have grown smarter and found a way to do it without making your disk explode.
We copy everything at the first backup, and the next time, only changes are copied.
But just the changes are not a full image! So the old unchanged files are hard-linked, making them
appear in the new backup as if they were copied as well.b But without taking twice the space. :)
This way each backup directory looks like a full snapshot of the data at the point.

Eg: Directories `day1` and `day2` are both apparently full backups. If you list them, all your
files are there. All the files, *as they were at the time*. So all the files are there, but just
the ones with different *inode* numbers are really taking place in disk, the others, are linked.

	day1                        day2
	|                            |
	|- 1550 unchanged.txt  --->  |- 1550 unchanged.txt
	`- 1327 changed.txt          `- 8702 changed.txt

	             data in disk:
	               - 1550 unchanged.txt
	               - 1327 changed.txt
	               - 8702 changed.txt

## How to use it?

The script receives one or more origin directories (where the data is), and a destination directory
(where it shall be saved) and some options. Optionally, a config file with a backup plan can also
be provided.

Minimal basic data to make the script work:

1. Origin directories
2. Destination directory
3. Action (backup, rotate, test)

`python backup.py --origin /home/fulano --origin /home/mengano --dest /media/usb-disk backup`

As it's `rsync` based, it is not necessary for either origins or destination to be local. You can
mix and chose to *push* your backup from your machine to a safer place, *pull* it from a host and
store it locally or both, get it from a remote machine and store it on another.

You can provide all the options on the command-line, but a more reasonable way to use the script is
to write a backup plan.
A plan is a named backup task. It defines origins, destination and options in the friendly YAML
format, and this way, only the plan file has to be passed to the program.

`python backup.py --plan backup-home.yaml backup`

See more about this in the *Plan* section.

### Paths

- Origin paths can be relative to the config file, if its present. They will be relative to the script otherwise.
- Destination will be redirected straight to rsync so it can be anything that rsync understands.
  Have in account that if rsync prompts asking password for ssh, it will stop the script when
  running from cron.

## Actions

The script accept the following *verbs*, which indicate what it should do:

- **test**: Tests the backup scheme. No data it's copied, no directories are created.
- **rotate**: Create weekly directories in *dest* directory and move old backups to them.
- **backup**: Performs a regular backup.

Usually rotate takes an option, which indicates how many backups it should be until moving them
to weekly directories.
Tests relies on the rsync option `--dry-run` so connection, logging and net data transfer will be also tested.

## The drawbacks

There's almost no inconvenience in this system except for the meta-data and directory space bloat
when performing really small backups (with delta changes of bytes) and dense directory trees.

1. You cannot hard-link directory entries, so they'll have to be re-created each time, and that
will be some extra megabytes per backup on the long run.

2. If you have to replicate a whole image of your disk by hard-linking files one-by-one, it can
take some time after each one of them has been consulted and linked when you have a very high
number of files.

Backing up really-freaking-dense directory trees or tons of tiny files may result in a lot of extra
space (compared to the real data size) being used just in structure and meta-data. This doesn't
make this backup system bad, just keep in mind that each time a backup is made, even if only few
bytes are change, it could end-up in 15Mb of new directories.

## The Plan file

The plan file supports each single command-line option in its *long* form.
For single options, just write `name: value`, for multiple options, the ones that can have more
than one value, you set a *YAML* list. For example, to set two paths as origins, you would write a
YAML list:

	origins:
	- /path/value
	- /path/other

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

A very usual disposition is to send your backup to a remote server or a NAS. This can be easily
done by adding *ssh* information for the *dest* directory, the server ip and the login user. The
existence of this info will make the script transform the path into a valid *ssh* url like
`user@host:/path/to/dest`.

	# Where to store the backups
	dest: /media/external/bk
	dest_host: 192.168.1.100
	dest_user: admin

	# Directories to be backed up
	origins:
	- /home/jvr/Dropbox
	- /home/jvr/.config

In this other example, we perform a similar task but backing up a remote host **the other way**.
Instead of sending data from a machine and storing it on other server, we pull it from other
*passive* computer and store it locally.

This other plan it's what I use to backup my smartphone on a local network through ssh.
The plan also sets some options `rotate_max`, `logfile` and the `verbose` level.

	# ssh backup

	dest: /home/jvr/backup/nexus

	origins:
	- /sdcard

	# ssh options for all origins
	origin_user: root
	origin_host: 192.168.1.11

	rotation_max: 5
	logfile: /home/arl/backup/nexus.log

	# Change permissions on the copy and follow symlinks
	rsync_args:
	- "--chmod=u+rwx"
	- "-L"

	excludes:
	- .cache/*
	- .thumbnails
	- .image-cache

The `rsync_args` option should also draw your attention, it takes options for rsync that are sent
straight to the command-line order; This is very important when backing up certain file-systems or
when you want to override some option set by default by the script with a `-no-OPT` rsync option.

	origins:
	- /home/fulano
	- /home/mengano

	dest: /var/backup

	origin_host: 192.168.1.2
	origin_user: user
	origin_module: user_host

	excludes:
	- "*music*"
	- "*video*"

We're using here the rsync's own protocol. This is a real set-up example to backup a *Windows 7*
box running a [cwRsync][] server. This is cake when one's have to backup lots of different hosts
and avoid re-configure each single machine when a change in the backup-policy its made.

## Options

The complete list of arguments:

		Usage: backup.py Usage: [options] [--plan plan] backup|rotate|test

		Options:
		-h, --help            show this help message and exit
		-p PLAN, --plan=PLAN  Backup plan definition.
		-o ORIGINS, --origin=ORIGINS
								Add location to backup.
		-d DEST, --dest=DEST  Where to store the backup.
		-m ROTATE_MAX, --max=ROTATE_MAX
								Max number of backups stored. Default 10.
		--host=ORIGIN_HOST    Host for origins if needed.
		-g ORIGIN_MODULE, --module=ORIGIN_MODULE
								Module for origins if needed.
		-u ORIGIN_USER, --user=ORIGIN_USER
								User for ssh origins if needed.
		-e EXCLUDES, --exclude=EXCLUDES
								Exclude patterns.
		-s MAX_SIZE, --max-size=MAX_SIZE
								Exclude big files. Default 500M.
		-a RSYNC_ARGS, --rsync-args=RSYNC_ARGS
								Extra args for rsync.
		-l LOGFILE, --logfile=LOGFILE
								Path to logfile to store log. Will log to stdout if
								unset.
		-j PRE_HOOK, --pre-hook=PRE_HOOK
								Order to be called before backup.
		-k POST_HOOK, --post-hook=POST_HOOK
								Order to be called after the backup.
		-v, --verbose         Verbosity. Default silent. -v (info) -vv (debug)


## Dependences:

- python2.6
- python-yaml
- rsync 2.6+

[cwRsync]: http://www.itefix.no/i2/cwrsync
