# filediff

Calculates differences between file trees in the same disk grouping by inodes.
It is useful when trying to know which files changes between strongly hard-linked structures.

## Concept by example

For example, given the following tree with two directories holding two files each:

	day1                        day2
	|                            |
	|- 1550 donotchanges.txt --> |- 1550 donotchanges.txt
	`- 1327 dochanges.txt        `- 8702 dochanges.txt

Where `day1/donotchanges.txt` and `day2/donotchanges.txt` are hard-linked and thereof are the same
file, pointing to the same data in disk. As opposite, each `dochanges.txt` is a completely different
file.

The output of `filediff day1 day2` would be:

	$ filediff day1 day2
	day1
	< day1/dochanges.txt
	day2
	> day2/dochanges.txt

Where all independent files under each tree are shown in a way that resembles the well known
`diff` unix tool.

# Options

There are several options that mostly perform size calculations and add extra information to the
output. Some of them are:

- **--dirs** **--onlydirs**: You cannot hard-link directories, so they'll always be different
  within different trees. You probably count with that, so the script's default behaviour is to
  ignore them, to avoid adding noise to the output. But sometimes you could want having directories
  in account, specially when calculating used space in large trees, when the accumulated size of
  all directory entries can be significant.

- **--group**: One line per real file, thats it, inode. If several files in the same tree are
  linked, they all appear in the same line, separated by semicolon. 
  Useful when concatenating with `wc -l` or there is lots of hard-links under the same tree.
  		$ filediff day1 day2 --group
		day1
		< day1/dochanges.txt
		day2
		> day2/dochanges.txt
		> day2/dochanges-link.txt

- **--size**: Shows file sizes in the output.
		$ filediff day1 day2 --size
		day1
		< 150B day1/dochanges.txt
		day2
		> 373B day2/dochanges.txt

- **--count**: Computes total sizes per each file tree:
		$ filediff day1 day2 --count
		day1
		< day1/dochanges.txt
		Total: 150B
		day2
		> day2/dochanges.txt
		Total: 373B

- **--left** **--right**: List just one of the sides.

The complete list:

		Usage: [options] DIR DIR

		Options:
		-h, --help     show this help message and exit
		-v, --verbose  Verbosity. Default silent -v (info) -vv (debug)
		-i, --inode    Show file inodes
		-g, --group    Group paths by inode. Multiple paths in one line
		-s, --size     Show file sizes
		-c, --count    Compute difference sizes
		-u, --human    Human readable sizes
		-L, --link     Dereference symbolic links
		-l, --left     Only left side. Don't print right side
		-r, --right    Only print right side. Don't print left side
		-n, --nolist   Don't print file list, just counters

## Dependences

- python 2.6
