# -*- mode: ruby -*-
# vi: set ft=ruby :

# Vagrantfile API/syntax version. Don't touch unless you know what you're doing!
VAGRANTFILE_API_VERSION = "2"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  
  config.vm.define "web" do |w|

    w.vm.box = "ubuntu/trusty64"

    w.vm.network "forwarded_port", guest: 80, host: 8000
    w.vm.network "forwarded_port", guest: 3000, host: 3000
    
    w.vm.network "private_network", ip: "192.168.33.10"
    w.vm.synced_folder "/Volumes/music", "/vagrant/mounts/music"
    w.vm.synced_folder "/Volumes/development/code/freshbeats-pi/mounts/beater_working", "/vagrant/mounts/beater_working"

    w.vm.provider "virtualbox" do |v|
      v.memory = 1024
      v.name = 'freshbeats_web'
    end

    w.vm.provision "chef_solo" do |chef|

      chef.add_recipe "mysql::client"
      chef.add_recipe "mysql::server"    
      chef.add_recipe "nginx"

      chef.add_recipe "beater"

      chef.json.merge!({
        :mysql => {
          :version => "5.6",
          :platform_family => "debian",
          :server_root_password => "dev"
        },
        :nginx => {
          :init_style => "init"
        }
      })
    end

  end

  config.vm.define "rpi" do |r|

    r.vm.box = "denis/archlinux32"

    r.vm.network "private_network", ip: "192.168.33.11"
    r.vm.synced_folder "/Volumes/music", "/vagrant/mounts/music"
    r.vm.synced_folder "/Volumes/development/code/freshbeats-pi/mounts/beater_working", "/vagrant/mounts/beater_working"
    
    r.vm.provider "virtualbox" do |v|
      v.memory = 1024
      v.name = 'freshbeats_rpi'
    end

    r.vm.provision "chef_solo" do |chef|

      chef.add_recipe "beater::beatplayer"

      chef.json.merge!({
        :beatplayer => {
          :environment => "prod",
          :mount_username => "myusername",
          :mount_password => "randompassword",
          :ssid => "myssid",
          :ssid_passphrase => "randompassphrase"
        }
      })
      
    end

  end

end
