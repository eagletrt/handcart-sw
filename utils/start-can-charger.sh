#!/bin/bash
sudo ifconfig can0 down
sudo modprobe can
sudo ip link set can0 type can bitrate 250000
sudo ip link set can0 up