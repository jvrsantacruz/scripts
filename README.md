# Personal scripts

This repository concentrates some small (sometimes tiny) useful scripts I write and use in my
day-to-day work. They're mostly in *Python* but most of them started as quick *Bash* one-liners or
scripts and the primitive version is also included.

Each script is in a separated directory including its own README file with instructions and
indications about its implementation.

## What they do?

This is a short description list of each script.

- **filediff**: Calculate differences between file trees by finding the exclusive files under each
  one by inode.
- **lists**: Copies music files in a playlist to a directory. Useful for portable file-based mp3
  players.
- **mp3hash**: Hashes files omitting their tag metadata, so the same song with different names can
  be recognized.
- **music-bd**: Updates Banshee/Clementine databases for rates, playcounts and skipcounts, so they
  can be maintained when changing between them or after a database reset.


## Why I upload them?

I use and update this small pieces of software constantly, so having them here kind of forces me to
maintain some order and documentation. Keeping the files under git also avoids the chance of
shooting myself in the foot.
