#!/bin/bash

sudo modprobe vcan
sudo ip link add dev can1 type vcan
sudo ip link set up can1
