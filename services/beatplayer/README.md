# beatplayer 

## Deploy 

`.env` has entries for both the container environment as well as the docker-compose 
runtime itself. 

**HOST_MUSIC_FOLDER**: music folder container volume source, configure separately 
**BEATPLAYER_PORT**: container port, also sets exposed port during build and the server listening port
**BEATPLAYER_LOG_LEVEL**: Python log level for beatplayer itself, debug, info, etc., case-insensitive
**BEATPLAYER_INITIAL_VOLUME**: beatplayer initial volume, default 90 

`build.sh` will handle setting ARCH for the alpine image based on the native architecture.
For a cross-build, this value can be overridden with CPU_ARCH on the command line 
to `armv6l` or `armv7l`, with all other values defaulting to the `x86_64` target.

```
./build.sh 
./run.sh -- -d
```

While `run.sh` will accept `docker-compose up` flags after the `--` separator, 
trying to `--build` here will cause problems due to missing build arguments. Please 
build with `build.sh` or modify it as needed.

## Architecture 

mpplayer.py 

MPPlayer 
  - RPC server
  - self.player :: BaseWrapper/MPVWrapper   
    - BaseWrapper manages a singleton of MPVWrapper 
    - exposes common player commands to the RPC server 
    - MPVWrapper communicates with the player process via unix domain socket 
    - self.socket_talker :: MpvSocketTalker singleton 
      - send(): new socket instance, adds request_id and sends
      - read(): accepts request_id and returns one related response
      - self.watch_thread: on MpvSocketTalker init, spins up and continuously reads and files socket output
  - self.health :: PlayerHealth
    - class instance for MPPlayer only
    - hosts register_client(callback_url)
      - maintains dicts of callback_url values for registered timestamp and health ping thread 
      - health ping thread accesses player singleton to get stats and posts info back to its callback_url
  - \_dispatch -> scans self.player and self.health 

During operation, output is generated from:
  - the service itself: mostly logging, not intended for user display 
  - the mpv process: actual playback output, should be presented as-is 
    - ProcessMonitor.run_in_thread starts on process creation, dies with it
    - PlayerHealth.ping_client checks PID and if the mpv process is alive 
  - the mpv unix domain socket: interaction with the mpv process, reading and setting properties, useful for controls/controlling display 
    - MpvSocketTalker.\_watch run continuously and serves 
      - PlayerHealth.ping_client which starts with client registration and reads properties to drive player display 
      - RPC server requests that set properties

thread map:

mpplayer.py 
  - on player selection, if mpv, then MpvSocketTalker.\_watch to read and index socket output forever 
    - starts on player selection, however there is nothing to read until a play 
    - could start (if not already running) on any read and die naturally if the socket becomes unresponsive 
  - on health.register_client, PlayerHealth.ping_client until client is unregistered / becomes unresponsive 
    - was originally a dead man switch for beatplayer service health 
    - has grown to be all player stats, and the call is parsed by both the health and player eat the web app 
    - built to support multiple clients, but since everything goes through the webapp, there will never be more than the one 
  - on mpv player play(), ProcessMonitor.run_in_thread to read subprocess stdout/stderr until it dies 
