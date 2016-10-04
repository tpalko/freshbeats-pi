=begin
	
	for chef provisioning:

		pacman -S rubygems

		wget https://aur.archlinux.org/packages/om/omnibus-chef/omnibus-chef.tar.gz
		tar -xvf omnibus-chef.tar.gz
		cd omnibus-chef

		wget https://aur.archlinux.org/packages/ru/ruby-bundler/ruby-bundler.tar.gz
		tar -xvf ruby-bundler.tar.gz
		cd ruby-bundler
	
=end

template "/etc/smb-credentials" do
  source "smb-credentials.erb"
  owner 'root'
  group 'root'
  variables({
     :username => node[:beatplayer][:mount_username],
     :password => node[:beatplayer][:mount_password]
  })
end

# - NOTE: omit "sec=ntlm" when mount point is on a Linux server
mount "/mnt/music" do

	device "//biereetvin/music"
	fstype "cifs"
	options "credentials=/etc/smb-credentials,sec=ntlm"
	action :enable

end

# - NOTE: omit "sec=ntlm" when mount point is on a Linux server
mount "/mnt/beater_working" do

	device "//biereetvin/development/code/freshbeats-pi/mounts/beater_working"
	fstype "cifs"
	options "credentials=/etc/smb-credentials,sec=ntlm"
	action :enable

end

bash "install-mplayer" do

	code <<-EOH
		pacman -S mplayer
	EOH

	user "root"
	action :run

end

# - These are the wireless settings..

template "/etc/systemd/system/network-wireless@.service" do
  source "network-wireless@.service.erb"
  owner 'root'
  group 'root'
end

bash "create-wpa_supplicant-conf" do

	code <<-EOH
		wpa_passphrase #{node[:beatplayer][:ssid]} #{node[:beatplayer][:ssid_passphrase]} > /etc/wpa_supplicant/wpa_supplicant-wlan0.conf
	EOH

	user "root"
	action :run
end

bash "enable-wireless" do

	code <<-EOH
		systemctl enable wpa_supplicant@wlan0
		systemctl start wpa_supplicant@wlan0

		systemctl enable dhcpcd@wlan0
		systemctl start dhcpcd@wlan0
		
		systemctl enable network-wireless@wlan0.service
		systemctl start network-wireless@wlan0.service
	EOH

	user "root"
	action :run

end

# - End wireless settings.

%w{ python-pip }.each do |p|
	package p
end

bash "install-requirements" do

	cwd "/vagrant/services/beatplayer"

	code <<-EOH
		pip install -r requirements.txt
	EOH

	user "root"
	action :run
end

template "/etc/systemd/system/beatplayer.service" do
  source "beatplayer.service.erb"
  owner 'root'
  group 'root'
  variables({
     :environment => node[:beatplayer][:environment]
  })
end

bash "enable-beatplayer" do

	code <<-EOH
		systemctl enable beatplayer.service
		systemctl start beatplayer.service
	EOH

	user "root"
	action :run
end

#https://wiki.archlinux.org/index.php/locale

#vi /etc/locale.gen
#uncomment en_US.UTF-8
#locale-gen
#localectl set-locale LANG=en_US.UTF-8

=begin
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

cp /etc/samba/smb.conf.default /etc/samba/smb.conf

mplayer -ao alsa -shuffle -playlist playlist.txt
=end