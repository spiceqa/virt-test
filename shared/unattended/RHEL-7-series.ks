install
#KVM_TEST_MEDIUM
#xconfig --startxonboot
#text
shutdown
lang en_US
keyboard us
network --bootproto dhcp 
rootpw 123456
firstboot --disable
#xconfig --startxonboot
user --name=test --password=123456
firewall --enabled --ssh
selinux --enforcing
timezone --utc America/New_York
bootloader --location=mbr --append="console=tty0 console=ttyS0,115200"
zerombr
KVM_TEST_LOGGING

clearpart --all --initlabel
autopart

%packages --ignoremissing
@base
@core
@development
@additional-devel
@debugging
@network-tools
@x11
@gnome-desktop
@fonts
@smart-card
gnome-utils
python-imaging
NetworkManager
ntpdate
watchdog
coreutils
usbutils
spice-xpi
virt-viewer
spice-vdagent
usbredir
totem
dmidecode
alsa-utils
-gnome-initial-setup
%end

%post
echo "OS install is completed" > /dev/ttyS0
grubby --remove-args="rhgb quiet" --update-kernel=$(grubby --default-kernel)
dhclient
chkconfig sshd on
iptables -F
echo 0 > /selinux/enforce
chkconfig NetworkManager on
#Workaround for graphical boot as anaconda seems to always instert skipx
systemctl set-default graphical.target
sed -i "/^HWADDR/d" /etc/sysconfig/network-scripts/ifcfg-ens*
sed -i "s/ONBOOT=no/ONBOOT=yes/" /etc/sysconfig/network-scripts/ifcfg-ens*
echo 'Post set up finished' > /dev/ttyS0
echo Post set up finished > /dev/hvc0
cat > '/etc/gdm/custom.conf' << EOF
[daemon]
AutomaticLogin=test
AutomaticLoginEnable=True
EOF
cat >> '/etc/sudoers' << EOF
test ALL = NOPASSWD: /sbin/shutdown -r now,/sbin/shutdown -h now
EOF
cat >> '/home/test/.bashrc' << EOF
alias shutdown='sudo shutdown'
EOF
%end
