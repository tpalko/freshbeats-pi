# Raspberry Pi

## The Host

sudo raspi-config, turn of starting x-server after boot 
curl -sSL https://get.docker.com | sh
/etc/resolv.conf DNS config

## The Server

sudo apt-get install -y mplayer telnet 
copy requirements.txt
pip install
\#template out the config file
\#write the rest of the files
\#install server into systemd
\#enable and start the service with systemd
\#run alsamixer to set output to non-zero, unmuted

/etc/docker/daemon.json:
  { "insecure-registries": ["frankendeb:5000"] }

docker login frankendeb:5000
