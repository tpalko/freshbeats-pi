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
