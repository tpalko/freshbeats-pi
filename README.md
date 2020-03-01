# freshbeats-pi
### Own What You Own

**Goals**
* learn
* tinker
* get confused

**Components**
* music playback API (services/beatplayer)
* music file management utility (services/freshbeats)
* socket IO server (services/switchboard)
* web interface (webapp)

### STOP!

This project is quite unfinished. Yes, if you have a magic touch, it will work. I
use it regularly, but I created it, and I think it only obeys me (on occasion)
because it owes me its life.

## Getting Started

This project is:

1. A web interface that provides
  - search and playback on any networked device of music files available on any
  network, provided the networks are networked
  - light management and classification of said music files, including personal
  review and ripping status
  - an interface for the utility (below) to rotate said music files on your mobile
  device
2. A command-line utility that
  - ingests information about a music collection from a filesystem
  - smartly (using survey info collected through the website) rotates your music
  collection through your mobile device
  - identifies and helps to remediate IDv3 tagging inconsistencies

### Collection Ingestion

**Requirements**
* a running MySQL database instance accessible from this code

First, probably, you want to ingest information about your music collection into
the database. You'll need a database and the utility `services/freshbeats/freshbeats.py`.

Go into `services/freshbeats/config` and copy `settings_example.cfg` to `settings.cfg`.

In your new settings file, set `MUSIC_PATH` and have a look at the entries in `files`.
These control what files the utility considers to be music files and what to skip.
Feel free to change these.

The rest of the settings are irrelevant for ingestion.

Then:

```
./freshbeats.py --help
```

The only option other than `-i`, which you'll use in a minute to ingest your collection,
is `--skip_verification`, which controls whether the script will check the files
for consistent IDv3 tagging, differences in file count and size since the last
ingestion, and mismatched SHA1 sums since the last ingestion. If this is your
first ingestion, probably `--skip_verification`. This script is idempotent, so
you can always come back and mess with your tags.

**Connecting to the database?** `freshbeats.py` directly uses Django models and the web app's
Django settings. Next stop, `webapp/config/settings_env.py`. You'll notice the
database connection is driven by environment variables. In the `webapp` folder,
copy `.env.example` to `.env` and edit your new `.env` file to fill in the
`FRESHBEATS_DATABASE_*` variables.

* single-node mode 
* containerized 

Also notice the two references to a music path: `web app .env's FRESHBEATS_MUSIC_PATH`
and `freshbeats.py settings.cfg's MUSIC_PATH`. The web app value overrides the
script value. One of them needs to be set.

That's it, I think. Go back to `services/freshbeats` and run:

```
$(cat ../../webapp/.env) && ./freshbeats.py -i -l
```

I don't know how big your collection is. This might take a while.

### Run the Web App

First, see "Connecting to the database?" above. Then,

Containerized:
```
docker-compose up --build
```

Uncontainerized:
```
cd webapp
pip install -r requirements.txt
./manage.py runserver
```

### Stand Up beatplayer (remote playback)

The Raspberry Pi module is expected to be running some flavor of Linux. This was tested with Arch ARM.

In the /deploy folder, find ansible scripts.

The `hosts` file has two host groups: `bootstrap` and `devboard`. The dev board (e.g. Raspberry Pi) module hostname should appear in this file.
The `host_vars/devboard.yml` has variables for the deploy user's name and public key, and the path to the python interpreter on the module.

Assuming, in this example, a password authenticated account `root` on the dev board, the command to provision said dev board with the deployment user and respective SSH key is:

	ANSIBLE_CONFIG=./ansible.cfg ansible-playbook -k bootstrap.yml --extra-vars "ansible_ssh_user=root"

NOTE: `hosts` should list the dev board hostname under `bootstrap`

Now the module is ready to receive provisioning through ansible by somewhat standard means.

As the deployment user:

	ANSIBLE_CONFIG=./ansible.cfg ansible-playbook site.yml

NOTE: `hosts` should list the dev board hostname under `devboard`

beatplayer runs on the Pi and is managed via systemd. The configuration is written by the chef-client provisioner when it executes the beater::beatplayer recipe.

Look in **/Vagrantfile** in the 'rpi' VM's chef.json.merge under [:beatplayer][:environment] for the environment setting. Chances are, the chef-client provisioner will not actually be used to provision the Pi, and so the steps in beater::beatplayer will need to be followed by hand.

There are also configuration steps to set up a WiFi USB dongle with DHCP.

The environment for this service is actually hardcoded to 'dev' in the class's __init__, however the 'prod' environment configuration file is available.

For my development setup, there is an additional folder share available to the RPi so it can simply run beater.py from in-place development code, rather than deploying it after every change. Alternatively, you can simply scp the files to the Pi. It doesn't really matter where they go - I put services/beatplayer at /usr/share/freshbeats/services/beatplayer

On your RPi (assuming it is on the network, the shares are mounted, and the code is in place):

	$ cd /where/the/code/lives
	$ ./mpplayer.py -e [dev|prod] -a $(hostname)

### Check-out Music on a Mobile Device

(coming soon)

### Fix Your IDv3 Tags

(coming soon)

### Update Your Collection

(coming soon)

## Architcture

From a high-level, the web app and utility file are laid out in reverse CLI-to-API style.
That is,rather than a command-line utility interacting with an API, this is a command-line
utility being used as a module by a web application to perform the same tasks
through a browser. This is largely due to the fact that a lot of what this does
is command-line oriented.

Playback deployment through the web app can look like this:

```
Client (your browser)
  |                                         |o|  home   |o|
  |                                         |0| theater |0|
  |                                         |0|  system |0|
  |                                                |
  V                                                |
Django Web App -------------------------> Pi (RPC server, beater.py)
(+Web App DB)                                      |
                                                   |
                                                   |
                                         file share (SMB/CIFS/whatever
                                           the Pi OS will talk to)
```

Mobile device media management can look like this:

```
Mobile device (your phone)
  |
  |
  | <-- SSH
  |
  |
freshbeats.py utility
```

Note that this is a reference implementation. The web app and file share can
(and does in my case) run on one machine. The Pi is any networked device with
ports that can run Python. The "home theater system" can be headphones. Everything
can run on one box.

## Get Some Prompt

import sys, os, django
sys.path.append('../../webapp')
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings_env'
django.setup()
from beater.models import *
album = Album.manager.find(name='Rage Against the Machine')

## State of Development

* Django 3.0
* architectural wrinkles
  - reliable state management within each component (web app, UI, beatplayer, switchboard)
    - fix mute/pause state, e.g. no-op if not playing, reset if mpplayer restarts or loses process, update UI according to actual process status 
    - pause should toggle color as mute/shuffle do, play should color when playing, maybe some keep color but show toggled status some other way
  - reliable awareness of state between components 
    - healthz endpoints everywhere
  - reliable error handling and messaging to the user and in logs 
  - uptime resiliency - plug and play 
  - dockerized (minimum: full scripted/ansible/whatever, bonus: k8s-ready)
  - flexible configuration 
  - testable components / single-node mode 
  - reference the 12 factor app, haha 
* features 
  * unified search and playback UX
  * unified CLI/UI, central API 
    * everything from the UI at the prompt (playback, search, mobile)
    * everything from freshbeats.py in the UI (ingestion)
  * admin dashboard
    * see beatplayer(s!), switchboard, devices + status
    * manage devices
  * record shop search mode
  * (test this) prevent delete for shopping albums (in DB but not on disk)
  * implement separate 'back' and 'start over' controls 
  * snappy UI controls
  * full playlist CRUD 
  * multiple playlists
  * keyboard controls
  * track log of played songs, so 'previous' actually gets previous 
  * tagging 
  * beatplayer gets four registrations if it goes down and comes back up 
  * extract additional output from player, show in scrolling window 
  * devices integration / support 
  * allow playlist to be scrolled, don't reset to current if scrolling 
  * artist/album grouping playlist display mode
  * mobile CSS 
  * fix discrepancy between sync/async player updates (volume vs. everything else)
  * tabbed search results 
  * TaHoBudDey integration 
  * youtube integration (youtube integrated search? at least handling youtube addresses in the playlist)
  * hibernate mode (health checks slow down over time when no user input recorded)
  * beatplayer API to support client registration management, soft restart, general state stuff 
* extra: 
  - remove devops cruft 
  - renaming / file organization 
    - beatplayer (services)         -> beater (API)
    - beater (webapp)               -> freshbeats (Django project)
    - freshbeats (services)         -> fresh (CLI) 
    - beatplayer (webapp module)    -> (no change, player views, controls and state, and beater state)
      - PlayerObj, Beater, Playlist -> separate python modules
    
  
## Act of Development

Each of the three services ('beater' web app, mpplayer.py RPC server, and freshbeats.py) have two environment configuration files: 'dev' and 'prod'. The biggest difference between these environment setups are the paths to network shares. Generally, 'dev' expects that the service is running inside a Vagrant VM, and so will look for the mounts in /mounts. 'prod' expects that the service is running on a deployed machine, real or virtual, and will look in the traditional /mnt folder.

The 'rpi' Vagrant VM is available for testing, however it is not currently configured with audio outputs, so it's not very useful for actually testing BeatPlayer (mpplayer.py). Also, the chef-client provisioner hasn't been fully tested on it. I generally just use the actual Raspberry Pi for testing and don't bother powering up the VM - hence the commented IP address and inclusion of the Pi's hostname in the 'beater' web app's 'dev' settings file.

# Appendix A: Tahobuddy CI

```
{
  \"repository_name\": \"freshbeats-pi\",
  \"local_path\": \"/path/to/freshbeats-pi\",
  \"build_image\": \"tahobuilder_docker\",
  \"build_cmd\": \"docker build -t freshbeats .\"
}
```
