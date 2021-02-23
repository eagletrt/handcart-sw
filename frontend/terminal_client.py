import requests
import time

SERVER_ADDRESS = 'http://127.0.0.1:5000/'

r = requests.get(SERVER_ADDRESS)

if r.status_code == 200:
    print("Connected to " + SERVER_ADDRESS)

r = requests.get(SERVER_ADDRESS + 'handcart/status/')

if r.status_code == 200:
    print("Handcart STATE is: " + r.json()['state'])

while(r.json()['state'] != 'STATE.READY'):
    time.sleep(1)
    r = requests.get(SERVER_ADDRESS + 'handcart/status/')
    print("Handcart STATE is: " + r.json()['state'])

if r.json(['state']) == 'STATE.READY':
    comm = input('Ready to charge, press y to start charging: ')
    if comm == 'y':
        # Sends request to backend
