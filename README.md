#freshbeats-pi 
###Own what you own. Keep it fresh.

This project is two things:

1. A web interface that controls search and playback of your audio files through a Raspberry Pi
	a. The interface also provides a survey through which you can begin classifying (judging) your music
2. A program that smartly rotates your music collection through your mobile device for your remote listening pleasure.
	a. This program listens to the survey results obtained in part 1a of this description.

### STOP!

This project is quite unfinished. Yes, if you have a magic touch, it will work. I use it regularly, but I made it and I think it only obeys me on occasion because it owes me its life. Your best weapons will be your understanding of network file sharing, firewalls, linux package managers, and your undying devotion to become one with the hundreds or thousands of albums you've accumulated over the years.

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

With all that, you really only need one machine to run the web application, your music folder shared on the network, an empty working folder shared on the network, and your Raspberry Pi. Oh yeah, don't forget that undying devotion.

### Development

Confusion can set in if you decide to, say, fork the project and start developing. For my development setup, there is an additional share available to the RPi so it can simply run beater.py from in-place development code. The Django app can run in the provided virtualized environment.

### Django Configuration

In /webapp/config/settings.py, set these values _from the POV of your web server_:

	MUSIC_MOUNT = "/mnt/music/"
	BEATPLAYER_SERVER = 'http://alarmpi:9000'
	PLAYLIST_WORKING_FOLDER = "/media/working_folder"
	PLAYLIST_FILENAME = "playlist.txt"

### RPi Configuration

	…
	
## Run

On your web server box:

	$ vagrant up
	$ vagrant ssh
	$ cd /vagrant/webapp
	$ sudo supervisord -n -c /etc/supervisor/supervisord.conf 
	
On your RPi:

	$ ./mpplayer
	
Visit:

	http://localhost:8000
	
