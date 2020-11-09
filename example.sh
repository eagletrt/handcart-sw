#!/bin/bash

#gnome-terminal - e python3 ./communication/handcart_server.py
#gnome-terminal - e python3 ./backend/connectionToServer.py
#gnome-terminal - e python3 ./frontend/connectionToServer.py

gnome-terminal -e "bash -c 'python3 ./communication/handcart_server.py;exec $SHELL'"
sleep 1
gnome-terminal -e "bash -c 'python3 ./backend/connectionToServer.py;exec $SHELL'"
sleep 1
gnome-terminal -e "bash -c 'python3 ./frontend/connectionToServer.py;exec $SHELL'"