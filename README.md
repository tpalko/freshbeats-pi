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

```
bower install jquery jquery-ui datatables
```

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

## Security and Multi-tenancy 

The system could be fully multi-tenant. The database collection can 
obviously be multi-tenant, so the app must permit registration and selection of 
ad-hoc devices to play the music (as long as the available music library matches the 
information in the database). The "player" device and the music library accessible to it 
are then associated with the tenant collection of music in the database. The 
application can even spot check the player against database items to gain some 
confidence that the association is valid, trusting in the device's positive response 
of course. 

The appearance of the music library database records in the local development case 
is contrived, actually, and the initial ingestion would ultimately also be self-service.
The ingestion tool would run on the device, more like an agent, and transmit synchronization
messages to the application supposedly via the same channels as the general player 
status/control messages. 

With no information to start, the user would provision some device that has a) a 
media player compatible with the agent or a custom connector implemented from 
BaseWrapper and b) network or local access to a library of music files.

The user would then 

1. install the agent on the device and configure networking appropriately to make the agent available to the Freshbeats application 
2. select "add device" in the freshbeats UI
3. enter the base URL of the agent running on the device 

With some prompting, maybe, then 

4. the agent will begin scanning the device and transmitting synchronization messages to the Freshbeats application 
5. Freshbeats will populate the database in association with the device (and, in turn, the tenant)


Already, we have several authorization and authentication issues.

* Authentication to Freshbeats (not immediately pertinent to ad-hoc device registration but as yet untouched)
* Authorization of Freshbeats with the agent on the device 
* Verification of the messages from the agent 

The agent's presence on the device is strictly read-only by design. There is no reason 
for any changes to be made, and therefore no reason to permit or enable the agent to do so.
Regarding authorization of Freshbeats with the agent, there are the issues of privacy 
and tampering - media should be playable only by the agent's origin server, i.e. 
when the user installs the agent, they are implicitly permitting whatever service 
backs the agent to control it. The agent needs a way of verifying the origin server.
This is typically done either with a secret or with an asymmetric keypair.

On behalf of the agent, it must be able to trust messages from Freshbeats. 
If the agent was initiating the exchange, it might make sense for it to assume the 
validity of Freshbeats and pass a random generated secret for Freshbeats to use 
on future communications. Then again, Freshbeats must also be able to trust messages 
from the agent, and Freshbeats supplying a key for the agent to use would also make 
sense. But neither side should be able to be solicited for a secret without the 
intervention of the user, who begins the chain of trust.

Agent:
* only Freshbeats can control and gain information

Freshbeats:
* only an agent identified by a user can synchronize the database and send status messages 

Actor A doesn't tell B how to send messages to A, or ask how to send messages to B
A asks B how B wants to send messages to A
B replies with a token 
Now A knows how to verify messages from B
But B doesn't know how to verify messages from A 
Can B ask A the same question? 
A could be a jerk 
B now knows about A, and asks A how A wants to send messages to B 
A replies with a token 
Now B knows how to verify messages from A, but that doesn't mean A is a good actor 
B is a good actor to Freshbeats, because the user said so

The Agent: "Here's How You Trust Me"
The user registers the agent with Freshbeats 
Freshbeats sends its public key and a callback URL to the agent at a special DMZ-type endpoint 
The agent encrypts a generated token with the public key and sends it to the callback URL 
Freshbeats can now accept messages from the agent

The agent needs a way to verify substantive messages from Freshbeats
Freshbeats: "I Know Your Secret"
This actually takes care of both sides 
User sets or agent generates a secret 
That secret is provided to Freshbeats _by the user directly_ not via messaging 
There is no soliciting the token from the agent

## Loosely Coupled Components 

### Desired Behavior 

Any number of devices may be operated by different users through a single 
instance of the application. If a user selects a device and plays a song, the device 
will begin playback on that song, regardless of what it might have been doing at 
that moment. By default, selection of different devices does not affect the user's selected 
playlist: the playlist comes along with the user for whatever device is selected. However,
the user can see what playlist and position a device is at, and choose to take on 
control. Each device operates independently of each other, allowing a user to move 
control freely between them or allowing multiple users to each control a device
without interfering with each other. 

Device selection by default is "auto": the first available (connected and ready)
device is selected. Manually choosing a device gives the option of either "intrusive", 
where the user's playlist, position, and other player state attributes are maintained,
or "participatory", where the user takes on the device's current playlist, position, 
and other player state attributes. When the device is automatically chosen 
for the user, the default is "intrusive" when the device player is stopped and 
"participatory" when the device player is playing. 

If Alice is playing playlist "trigonometry" through auto-selected device A, but device 
B is available but not playing anything at the moment, and device A then stops responding,
device B is set to play "trigonometry" at the same position.

In the same scenario, if device B happens to already be playing something, Alice's 
view only reflects the down state of device A.

In the original scenario, if neither device A or B aren't actively playing but 
A becomes unavailable, B is automatically selected. If Alice were to press "play",
device B would then begin playback. 

Device selection: auto 

Scenario 1: 
Current device: stopped 
Alternate device: stopped 
  - whichever device is available will be selected for the user intrusively

Scenario 2:
Current device: playing 
Alternate device: stopped 
  - if current device becomes unavailable, the alternate device is intrusively selected and playback continues there 

Scenario 3:
Current device: playing 
Alternate device: playing 
  - if the current device becomes unavailable, no auto-selection occurs, current status is shown 

Device selection: manual 

Scenarios 1 and 2 are identical.
Scenario 3 results in a participatory selection of whichever device is selected.

By default:
  If a device is playing and is selected either automatically or manually, the result is a participatory selection.
  If stopped, intrusive.

Player.device is global - whoever is looking at a device gets the same Player state. Users do not have player state, 
but this value is reassignable based on user actions. It may make more sense for Device to have a Player FK than 
for Player to have a Device FK.

All devices are monitored by registering with the agent and accepting health reports.
The selected device for all sessions is known via the Session model.
If 
  * a device changes state from ready to notready
  * an alternative device is in ready state 
    * for each session has this device selected on "auto": 
       * the selected device is updated to the alternative device 

When a selected device changes, one of two things will happen:

* (device assigned is playing): the session selected Device is set and the UI reflects the existing Player state 
  - nothing needs to change in the database or in any device calls - the updated selected device will causes the UI to be updated with any events or status changes relevant to the device
* (device assigned is not playing): the session selected Device is set, and the Device Player is set to the user's previous Device Player 
  - Device.player_id is reassigned 
  - the session selected device is manipulated via the Session model and published to the UI 
  - calls are made to the devices to match state  
    - a generalized "state" call is made to set volume, shuffle, mute, etc.
    - if player state is playing, the 'play' call is sent to the new device with the start position, volume, etc.


A playlist remains selected for a user unless the user changes it.

Different users can have different playlists selected.
Player operations 
A playlist should be navigable despite a lack of an available player. 
Regardless of how a player is chosen, the current playlist 
and position from the previously selected player is applied to the new one.


Any number of beatplayer agents may be registered. 
Any number of playlists may be created. 
Any number of sessions may be interacting with the server. 
Agent-to-playlist is many to many. 
  - multiple agents can be operating on a given playlist 
  - an agent can operate (have state) on multiple playlists
An agent can only be active with one playlist at a time
Only one agent may be active with a UI at a time - this drives the header player display 



This means 
if the active player is changed, the

A Device/Player has an active Playlist, and a user session has an active Device/Player. 
The user chooses the Device/Player or it is chosen automatically. The Playlist This is set by choosing a Device/Player through 
the UI and then selecting a Playlist and playing a PlaylistSong. Once the 'play' command 
has gone through to the Device/Player and the current PlaylistSong on the Player is 
set, future selections of that Device/Player will load that Playlist. Selection of 
a Playlist or playing a PlaylistSong have no effect if a Device/Player is not chosen. 
Playing a Song will automatically splice or add it into the current Playlist. If there is 
no Playlist, playing a Song will create a new Playlist and operate on it.

The header player display shows all available devices and by default the first available 
is selected (auto), though any may be chosen regardless of status. A selected device 
will then drive the playlist display, that of the playlist currently associated with the player.

Playlist 1 .. n Agent n .. 1 Session 

Device: the physical component of the Agent 

Player: the operational state component of the Agent 
  - Device
  - PlaylistSong: the current item for the Player, implies Playlist  

Playlist 

PlaylistSong 
  - Playlist 

PlaylistSong-Player: remembers a Player position on a Playlist 
  - PlaylistSong 
  - Player

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

youtube-dl 

http://ytdl-org.github.io/youtube-dl/download.html
sudo curl -L https://yt-dl.org/downloads/latest/youtube-dl -o /usr/local/bin/youtube-dl
sudo chmod a+rx /usr/local/bin/youtube-dl
