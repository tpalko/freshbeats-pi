# beatplayer 

Both the `docker-compose` environment as well as the container environment can be 
set with `.env`, as long as the values require no interpolation or evaluation. Environment 
requiring processing can be set on the command line. 

**docker-compose environment**
* ARCH: docker image tag 
* HOST_MUSIC_FOLDER: volume for /mnt/music within the container 

**container environment**
BEATPLAYER_LOG_LEVEL: debug, info, etc. 
BEATPLAYER_INITIAL_VOLUME: starting volume

The alpine image is built on native architecture with `build.sh`. If a cross-build 
is required, or `uname -m` does not yield a valid alpine tag, ALPINE_ARCH can 
be passed as a --build-arg.

 environment can be passed on the command line, i.e. 

ARCH=$(uname -m)
HOST_MUSIC_FOLDER

Build and tag the image specific to the architecture on which it will run.

```
ARCH=$(uname -m) docker-compose up --build -d
```

Mount the network share so the player has access to the audio files.

```
mkdir -p /mnt/music
sudo mount -o "user=<username>" //server/share /mnt/music
```
