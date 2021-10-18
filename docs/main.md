# Handcart Documentation

## Index

-   [Structure](#structure)
-   [Resources & Useful links](#resources)

## Intro

The handcart is the device that is responsible of transporting and charging the car's accumulator. It is based on three main components:

-   Brusa NLG513 charger, that is the actual charger
-   Raspberry pi 4 to run the software
-   High Voltage Accumulator

The rasp is connected via CAN Bus with the BMS in the accumulator and with the Brusa charger. The software of the handcart is responsible of all the processes to ensure a good and safe charge.

## Abbreviations

-   BMS, porco, acc -> accumulator
-   HV -> High Voltage
-   rasp -> raspberry
-   FSM -> Finite State Machine
-   TS (on, off) -> Tractive system (HV) (on o off)

# Software

## Overview

![General diagram](https://lucid.app/publicSegments/view/04f173a9-55f8-42e4-9aa7-747b02ec5147/image.jpeg)

The software is written in python and javascript. It's divided in two parts, respectively frontend and backend. The backend is responsible to manage the charge and to communicate with the devices, and it also hosts a webserver for the frontend.

## Backend

The backend is the part of the software that is responsible to manage the charge and to communicate with the devices, it also hosts a webserver to serve pages and data to the frontend.
Basically it is a python script that becomes a process, then it splits itself in three threads.

### Threads

The three threads are:

-   The state machine, aka the main thread
-   The flask webserver
-   The CAN read/write process

The three threads have an class istance that they can access which is in shared memory, accessed with a lock.
Other types of communication are two queues:

-   A queue for can msg send between FSM thread and CAN thread
-   A queue for can msg recv between FSM thread and CAN thread
-   A queue for command send between web server and the FSM

### Main thread with FSM

The FSM is based on multiple states:

-   CHECK: It is a state where the presence of the BMS and the BRUSA are checked, if they are both present it will pass to next state
-   IDLE: Both devices are connected and ready to rock, a precharge command is waited
-   PRECHARGE: Accumulator is asked TS ON, wait until a confirmation is received
-   READY: Accumulator is in TS ON, brusa is ready, waiting for a charge command
-   CHARGE: The charge is enabled
-   C_DONE: The charge is finished
-   ERROR: An error state, the charge (if enabled) is stopped, the BMS is asked to TS OFF, the PON of brusa is set to OFF

Note that in each state there's a check over errors from the can, if an error is found, the next state will be ERROR

#### STATE:CHECK

The presence of BMS and BRUSA is checked, if both are present, goto IDLE

#### STATE:IDLE

Both devices are connected and ready to rock, a precharge command is waited.

#### STATE:PRECHARGE

A TS ON can message is sent to BMS HV, which will do the precharge. In this state we will check if the bms will finish the precharge. Once it did so, the FSM willl go to READY state.

#### STATE:READY

The TS is on, we are waiting to receive the charge command from the webserver. We countinously check the queue for new messages.

#### STATE:CHARGE

In this state the charge is enabled, to do this, a variable named "can_forward_enabled" is set to True. This variable is shared between the FSM trhead and the CAN thread.
In the can thread, a check over can_forward_enabled is made, if it's False it will periodically send an empty CAN message to brusa (this is important to keep the link alive, otherwise the brusa will go in an error state if no msgs receivedin 300ms)
If it's True, it will send an enable charge command to brusa with the voltage and current settings. For more info check the brusa CAN messages matrix.

#### STATE:C_DONE

The charge is done, TS is still on, waiting for user input.

#### STATE:ERROR

Something triggered an error, we have to turn off everithing that could be dangerous. The method "staccastacca()" is called. Where a TS_OFF message both for chimera's and fenice's accumulator is sent. The message is sent until a confirmation about the fact that the TS is OFF is received.
In the staccastacca method also the PON is disabled

#### The canread object

The 'canread' object is an istance of a class that is thought to store all the information of the BMS, BRUSA, CAN and others. It is also used to process all the CAN messages. The CAN thread passes the can messages in the CAN queue and the FSM thread checks for new messages in the queue at each cycle, if so the message is processed in the canread object using a method. The canread object is accessed only by the thread of the FSM, the other threads access a copy of that object that is called shared_data.
This is done for safety reason and to assure a fast access without lag to the main thread, as this object contains error state variables.

### Flask HTTP server

This is the server that serve the requests received from the frontend. It uses the shared_data object to retrieve the data from the FSM thread

## Frontend

## Brusa NLG513

## Raspberry configuration

Follow the guide
here [Rasp config](https://github.com/eagletrt/chimera-steeringwheel/blob/1402786b2e5fb6a07b8e8e68f7986f989c5b448c/tools/README.MD)
. The password of the raspberry is "handcartpi"

# Hardware

## Electrical wiring

## Handcart PCB

# BRUSA NLG5 Charger deep dive

The brusa can be controlled using CAN or can be programmed to be used without the CAN.
For our purposes we will control it over CAN BUS.

## Serial connection

To connect with brusa both for debug and/or change the settings we can use the serial interface.
To do so, you have to have an USB to serial adapter, connected to the pins of the BRUSA's connector, check the brusa manual. There are specific settings to set up the serial connection, in german they're called anschlusseinstellungen:

-   Baudrate: 19200
-   Data bits: 8
-   parity: none
-   stopbits: 1
-   protocol: Xon/Xoff

If you are on windows, let the serial COM settings as default, but edit the putty settings, i got
some problems otherwise.
Very important : i don't know why, but if you are going to use ChargeStar software you need
to change the COM port to COM1, otherwise the brusa will not be recognized by the program.
Note that the serial works only if the board on the brusa is fed with 12 volts via the proper pin
2 AUX or with the main power.

to use the serial monitor you have to properly connect and setup the serial, then, use putty on
windows or minicom on linux to connect to it. You will asked with a pasword, which is "monitor"

## ChargeStar software

With the ChargeStar software you can program a charging profile, set various parameters and
change some configuration of the brusa, see the brusa's manual for all the infos. Via ChargeStar
you can also set the mode to CAN, very useful to control the charge via can. The ChargeStar
software will run only on Windows XP or Windows Vista, obviously we'll chose XP, you can
run a virtual machine on virtualbox and do the USB-passthrough of the serial to USB adapter.
I read that somebody had issues with ChargeStar using the 64 bit version of windows, but for
me worked fine. Note that i ran in some problems uploading a custom setting to the brusa:
sometimes when the settings are uploaded, the brusa gives an NVSRAM CRC error, the only
possible fix is reupload the settings to brusa changing some parameters a bit. I'm still not sure which parameter is causing problems, so change them randomly a bit and it should work after some
tries. If you see, some input fields don't accept values with the "." not sure why.

## Connecting by CAN

Connecting with CAN allows to monitor the message outputed by the brusa and (if properly
configured) to set some parameters for charging. The CAN connection has to end with a 120
Ohm resistor, otherwise the messages will keep bouncing (kinda), trust me, it is necessary.
See the full CAN matrix in the manual.
By default the CAN is at 500kbps, unless differently specified in config file with ChargeStar. As
i saw, brusa send messages just when the PON pin is set to HIGH (>5V). To set and enable the
charge via can you have to send periodically a can message named NLG5_CTL see details on
the can matrix.
Note that the endianess is big (motorola).

# Resources & Useful links

-   [here](https://www.brusa.biz/_files/drive/02_Energy/Chargers/NLG5/NLG5_BRUSA.html) you can find BRUSA's CAN messages
-   For pork's can messages search on other E-Agle's repo
-   [Fake pointers in python](https://realpython.com/pointers-in-python/#simulating-pointers-in-python)
-   [Python threading API](https://docs.python.org/3/library/threading.html)
-   [Bootstrap dashboard template](https://getbootstrap.com/docs/4.5/examples/dashboard/)
-   [JS Charts](https://www.amcharts.com)
-   [Rasp config](https://github.com/eagletrt/chimera-steeringwheel/blob/1402786b2e5fb6a07b8e8e68f7986f989c5b448c/tools/README.MD)
-   [Charge state machine of BMS](https://github.com/eagletrt/chimera-bms/blob/sw-charging/src/Src/chg.c)

## Diagram links

https://lucid.app/lucidchart/invitations/accept/dbc53a3d-c901-4d6a-a692-972de6713d43

https://www.raspberrypi.org/documentation/hardware/raspberrypi/spi/README.md
