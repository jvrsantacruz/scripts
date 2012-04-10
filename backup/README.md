Automatic rsync based backup plans. 
One script for all.

Dependences:
	python-yaml

Script:

The script receives just origin directories, destination and backup options or a config file with plan(s).

python backup.py --origin /home/fulano --origin /home/mengano --dest /media/usb-disk

- Origins paths can be relative to the config file if present. Relative to the script otherwise.
- Destination will be redirected straight to rsync so it can be anything that rsync understands.
  Have account that if rsync prompts asking password for ssh, it will stop the script when running from crontab.

A plan is a named backup task. It includes origin directories, destination and options.

	origins: 
	- /home/fulano
	- /home/mengano

	excludes:
	- "*music*"
	- "*video*"

	dest: /var/backup

	origin_host: 192.168.1.2
	origin_user: arl
	origin_module: casa

	rotate_max: 10
