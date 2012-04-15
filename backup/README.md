# Backup

Rsync based backup plans. 
One full image directory per backup, only changes are stored, the rest is hard-linked.

## How it works?

### The perfect backup

The perfect backup plan would save absolutely everything each time it's called.
One complete snapshot per backup call, with each being a perfect copy of your machine at the time.
This way, accessing to old versions and restoring them would be completely straightforward.
__Sadly, this is unpractical__. You would harvest your disk and run out of space very soon.

### The almost-perfect backup

So we just have grown smarter and found a way to do it without making your disk explode. 
We copy everything at the first backup, and the next time, we copy the changes only.
But just the changes are not a full image! So we hard-link the old unchanged files, making them
appear there, in the new backup as if they were copied as well again, without taking twice the space. :)
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

The script receives one or more origin directories (where is the data), and a destination directory
(where should be saved) followed options or a config file with a backup plan.

Minimal basic data to make the script work:
1. Origin directories
2. Destination directory
3. Action (backup, rotate, test)

`python backup.py --origin /home/fulano --origin /home/mengano --dest /media/usb-disk backup`

As it's `rsync` based, it is not 

But a more reasonable way to use the script is to write a backup plan.
A plan is a named backup task. It defines origins and destination and options in the friendly YAML
format.

`python backup.py --plan backup-home.yaml backup`

In the next example we can backup through *ssh* some user directories to another machine

	# Where to store the backups
	dest: /home/arl/sdbk/bk

	# Directories to be backed up
	origins:
	- /home/jvr/Dropbox
	- /home/jvr/.config

	exclude:
	- ".dropbox"
	- "*.cache"

In this other example, we perform a similar task but **the
other way**, instead of sending data and storing it on other server, we pull it from other passive
computer and store it locally.
We're also using the rsync's own protocol. This is a real set-up example to backup a *Windows 7*
box running a [cwRsync][cwRsync] server. This is cake when one have to backup lots of different
hosts and avoid to re-configure each single machine when a change in the backup-policy its made.

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

	# Extra rsync args, they go straight to rsync
	#rsync_args:

	# Store in weekly dirs after 20 backups
	rotation_max: 20

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
2. hard-links are cheap, but not free. A hard-link means more that one file-descriptor pointing to
a single set of blocks in disk. But file-descriptor have its size as well.
3. If you have to replicate a whole image of your disk by hard-linking files one-by-one, it can take
some time after each one of them has consulted and linked when you have a very high number of files.

Backing up really-freaking-dense directory trees or tons of tiny files may result in a lot of extra
space (compared to the real data size) being used just in structure and meta-data. This doesn't
make this backup system bad, just keep in mind that each time a backup is made, even if only few
bytes are change, it could end-up in 15Mb of new directories.

## Dependences:

- python2.6
- python-yaml
- rsync 2.6+

[cwRsync]: http://www.itefix.no/i2/cwrsync 
