# commands to enable the hotspot on the carrellino (needs wifi usb key)
sudo nmcli d wifi hotspot ifname wlxacf1df10b92c ssid carrellino password <PASSWORD>
nmcli con modify Hotspot connection.autoconnect true
