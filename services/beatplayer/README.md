# beatplayer 

Build and tag the image specific to the architecture on which it will run.

```
ARCH=$(uname -m) docker-compose up --build -d
```

Mount the network share so the player has access to the audio files.

```
mkdir -p /mnt/music
sudo mount -o "user=<username>" //server/share /mnt/music
```
