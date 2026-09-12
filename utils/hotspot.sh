# commands to enable the hotspot on the carrellino (needs wifi usb key)
sudo nmcli d wifi hotspot ifname wlan0 ssid carrellino password HandcartPower69?
nmcli con modify Hotspot connection.autoconnect true
