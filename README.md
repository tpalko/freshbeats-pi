#freshbeats-pi 
###Own what you own. Keep it fresh.

This project is two things:

1. A web interface that controls search and playback of your music files - playback commands target a remote service, in this case, one running on a Raspberry Pi which is connected to a home theater system
	a. The interface also provides a survey through which you can begin classifying (judging) your music
2. A program that smartly rotates your music collection through your mobile device for your remote listening pleasure.
	a. This program listens to the survey results obtained in part 1a of this description.

### STOP!

This project is quite unfinished. Yes, if you have a magic touch, it will work. I use it regularly, but I created it, and I think it only obeys me (on occasion) because it owes me its life. Your best weapons will be your understanding of network file sharing, firewalls, linux package managers, and your undying devotion to become one with the music you've accumulated over the years.

## Setup

Admittedly, this project has some serious configuration complexity. The biggest challenge I've had is simply keeping an understanding of what is where. 

It basically looks like this:

<pre>
Your browser (client)
	|
	| basic page requests
	| polling player status (soon to be moved to the server)
	| AJAX requests for the player			                       |o |                     | o|
	|											                   |{}| home theater system |{}|
	|											                   |{}|    |                |{}|
	|			    			player commands                            |
	V			 			player status queries                          |
Django Web App -------------------------------------------------> <b>beater.py RPC server</b> (running on the pi)  
(+Web App DB)						                                 ^
   \		&                   write MP3s 	                        /
	\	freshbeats.py service -----------------> mobile device     /
	\ 			    ^       					                  /
     \   			 \  	      				                 /
	  \		 		  \		 					                /
write playlist file	   \		                    read playlist file
		\			update db 		                     read MP3s
		 \  		 read MP3s 		                         /
		  \  			  \			                        /
		   \  			   \			                   /
		 	V	        <b>CIFS "music" share</b> (holds your MP3s)
	      <b>CIFS "working" share</b> (holds the playlist text file)
</pre>

With all that, you really only need one machine to run the web application, your music folder shared on the network, an empty working folder shared on the network, and your Raspberry Pi (or some computer connected to speakers). 

Oh yeah, don't forget that undying devotion. (remember?)

### Development

Each of the three services ('beater' web app, mpplayer.py RPC server, and freshbeats.py) have two environment configuration files: 'dev' and 'prod'. The biggest difference between these environment setups are the paths to network shares. Generally, 'dev' expects that the service is running inside a Vagrant VM, and so will look for the mounts in /mounts. 'prod' expects that the service is running on a deployed machine, real or virtual, and will look in the traditional /mnt folder. 

The 'rpi' Vagrant VM is available for testing, however it is not currently configured with audio outputs, so it's not very useful for actually testing BeatPlayer (mpplayer.py). Also, the chef-client provisioner hasn't been fully tested on it. I generally just use the actual Raspberry Pi for testing and don't bother powering up the VM - hence the commented IP address and inclusion of the Pi's hostname in the 'beater' web app's 'dev' settings file.

#### 'beater' web app

This is started via supervisor. Look in **/webapp/config/wsgi.py** for the environment setting. See [Supervisor](http://supervisord.org/).
	
#### mpplayer.py (BeatPlayer) RPC server

This runs on the Pi and is managed via systemd. The configuration is written by the chef-client provisioner when it executes the beater::beatplayer recipe. Look in **/Vagrantfile** in the 'rpi' VM's chef.json.merge under [:beatplayer][:environment] for the environment setting. Chances are, the chef-client provisioner will not actually be used to provision the Pi, and so the steps in beater::beatplayer will need to be followed by hand. Note there are configuration steps to set up a WiFi USB dongle with DHCP.

#### freshbeats.py

The environment for this service is actually hardcoded to 'dev' in the class's __init__, however the 'prod' environment configuration file is available.
	
For my development setup, there is an additional folder share available to the RPi so it can simply run beater.py from in-place development code, rather than deploying it after every change. Alternatively, you can simply scp the files to the Pi. It doesn't really matter where they go - I put services/beatplayer at /usr/share/freshbeats/services/beatplayer
	
## Quik(-ish) Start

**First, edit /Vagrantfile to reflect your network, i.e. where your network shares are. There are two 'synced_folder' declarations in the 'web' VM block.**

Once Vagrantfile is correct, this will provision the 'web' VM:

	$ vagrant up
	
Now ssh in and run FreshBeats to populate the database with your music:

	$ vagrant ssh web
	$ cd /vagrant/services/freshbeats
	$ python freshbeats.py -u 

And finally, run the web app:

	$ sudo supervisord -c /etc/supervisor/supervisord.conf 
	
On your RPi (assuming it is on the network, the shares are mounted, and the code is in place):

	$ cd /where/the/code/lives
	$ ./mpplayer.py -e [dev|prod] -a $(hostname) 
	
Visit:

	http://localhost:8000
	
## Future Development

Several usability issues have prompted me to sketch a redesign of how I really want the front-end to behave.

### header
* player box:
	* show playlist name, length and place in queue (x out of y) 
	* show prev, current (highlighted), and next tracks
	* show play status (playing, stopped, paused)
	* show play controls (play, stop, pause, prev, next, first)
		- 'surprise' feature chooses a random song and plays it immediately
		- 'skip to next artist' or 'skip to next album' moves the cursor to the next song of a different artist or album
* nav:
	* search
	* playlist
	* mobile
	* config
	* survey
	
### search page
* live search, display results as you type
* results grouped as 'artists', 'albums', and 'songs'
* artist can be clicked to expand and show full artist details -> albums, songs
* album can be clicked to expand and show songs
* songs, albums, or whole artist collections can be played immediately, spliced after the current song, or enqueued at the end
	- default action is to the current playlist, but a second set of controls allow addition to other playlists
	- real time updates on playlist place in queue and prev/current/next
	- albums and artists can be added to the playlist in any fashion as pre-randomized

### stats page
* presets
	* recently added
	* recently checked-out
	* favorites
	* ripping problems, mislabeled, incomplete
	* unrated
	
### playlist page
- playlist CRUD
- a single list can be drag/reordered

### playlist builder page
Plays a random song, 5-10 seconds into track. User interacts with controls to build playlist.

* quick method: pre-select a single playlist to build. controls are 'keep' and 'pass'. either choice skips to the next song. 
* exhaustive method: define one or more playlists. controls are toggle buttons for each playlist and 'next'. 

### mobile page
* see what's on mobile
	* by database or live read?
	- a flag can be set here to keep the album on the mobile device on the next exchange
* exchange
	- initiates survey 
		* prompts for feedback on each album, one post at a time
		- each song for an album prompt can be 'played now' -> plays ten seconds of the middle of the song and returns playback to whatever was playing before
		- flags can be set on an album for 'incomplete', 'ripping problems', 'mislabeled'
		- a rating can be set for an album
		- a flag is available to keep the album on the mobile device on the next cycle
* refresh (recopies everything it thinks is checked-out)

### command line mobile?
* CLI for 
	* reading mobile inventory, free space
	* exchange
	* refresh
	
### admin
* control mobile settings
* any runtime configuration