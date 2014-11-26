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

The 'rpi' Vagrant VM is available for testing, however it is not currently configured with audio outputs, so it's not very useful for actually testing beatplayer.py. Also, the chef-client provisioner hasn't been fully tested on it. I generally just use the actual Raspberry Pi for testing and don't bother powering up the VM - hence the commented IP address and inclusion of the Pi's hostname in the 'beater' web app's 'dev' settings file.

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
	
