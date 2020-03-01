'''
# mount -t vfat /dev/sdb /mnt/phone -o uid=1000,gid=1000,utf8,dmask=027,fmask=137

productid
    708B - windows phone portal
    7089 - windows media sync
    7087 - usb mass storage
    7090 - charge only

Attaching the device to the computer will list it with the chosen function's productid under 'VBoxManage list usbhost' as 'busy'
The device will also show in virtualbox's settings/usb filter menu
Selecting it in the filter menu does nothing, until the VM is powered on, at which point it will be listed as 'captured'
Even after VM power off or removal of the filter, the device will remain 'captured' until virtualbox is closed and restarted

6/26/2015

Installed mtpfs (and gvfs may have already been installed).

gvfs-mount -li

will list all available virtual filesystems - when connected (at least via MTP) an Android device will show.

sudo mtpfs [mount point]

will detect MTP filesystems and do what it can to mount them.

e.g.

sudo mtpfs mtp:host=%5Busb%3A008%2C008%5D

device mounted at:
/run/user/1000/gvfs/mtp:host=%5Busb%3A008%2C008%5D/Internal storage

7/25/2015

plug in android device
ensure device is connected MTP
ensure device shows as mounted
$ gvfs-mount -li | grep Android -A10
create mount point
$ sudo mkidr /media/android
mtpfs mount
$ sudo mtpfs -o allow_other /media/android

8/26/2015

https://wiki.cyanogenmod.org/w/Doc:_sshd

(going through SSH to device rather than MTP - works on wifi!)

but 'shell' user is really weak

1/16/2016

/storage/sdcard0 -> /storage/emulated/legacy (home folder)
/storage/emulated/legacy -> /mnt/shell/emulated/0

'''
