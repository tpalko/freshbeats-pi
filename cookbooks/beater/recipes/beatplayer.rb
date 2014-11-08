/etc/wpa_supplicant/pbjt.conf
/etc/systemd/system/network-wireless\@.service

? /etc/conf.d/network@wlan0

/etc/dhcpcd.conf
/etc/wpa_supplicant/wpa_supplicant.conf 


systemctl status wpa_supplicant@wlan0
systemctl status dhcpcd@wlan0
systemctl status network-wireless@wlan0

systemctl enable wpa_supplicant@wlan0
systemctl enable dhcpcd@wlan0
systemctl enable network-wireless@wlan0

ip link show wlan0

5: wlan0: <BROADCAST,MULTICAST> mtu 1500 qdisc mq state DOWN mode DEFAULT group default qlen 1000
    link/ether c4:3d:c7:81:18:0a brd ff:ff:ff:ff:ff:ff

ip link set dev wlan0 up

5: wlan0: <NO-CARRIER,BROADCAST,MULTICAST,UP> mtu 1500 qdisc mq state DOWN mode DEFAULT group default qlen 1000
    link/ether c4:3d:c7:81:18:0a brd ff:ff:ff:ff:ff:ff

wpa_supplicant -B -i wlan0 -c /etc/wpa_supplicant/pbjt.conf

5: wlan0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP mode DORMANT group default qlen 1000
    link/ether c4:3d:c7:81:18:0a brd ff:ff:ff:ff:ff:ff

dhcpcd wlan0

5: wlan0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP mode DORMANT group default qlen 1000
    link/ether c4:3d:c7:81:18:0a brd ff:ff:ff:ff:ff:ff


wpa_passphrase PeanutButterJellyTime 1dlg3ah1dl751a > /etc/wpa_supplicant/pbjt.conf

cp /etc/samba/smb.conf.default /etc/samba/smb.conf

mplayer -ao alsa -shuffle -playlist playlist.txt