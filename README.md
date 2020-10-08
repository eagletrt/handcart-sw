# handcart - Fenice
This is the repo for the handcart of Fenice

## structure
![General diagram](https://app.lucidchart.com/publicSegments/view/5d5eb5a3-77bc-44d1-b641-f867606ba91e/image.jpeg)

![Communication diagram](https://lucid.app/publicSegments/view/ad0abc76-47aa-48bb-9229-563d7b6c2a0f/image.jpeg)

### diagram links
https://app.lucidchart.com/invitations/accept/7fbd23c5-16c0-4441-8aa8-d0963f368066

https://lucid.app/invitations/accept/653e7b85-554d-4b44-bffd-f446f46eb0ba


# SETUP

### Using Ubuntu 20.4

- Python 3.8
- pip3 20.2.3
- protoc 3.13.0
- pip3 protobuf 3.13.0
- pip3 grpcio 1.32.0

> WARNING: After [installation](#installation), if the pip protobuf and the
> protoc version are different (usually pip is the older one) you have to
> update it by ```pip install --upgrade protobuf```
> (check versions using ```pip3 show protobuf``` and ```protoc --version```).

## Installation

### Python 3
```sudo apt-get install python3.8```

### pip3
```sudo apt-get install python3-pip```

### protoc
Download the python ```.zip``` at
[this link](https://github.com/protocolbuffers/protobuf/releases),
then run the following commands:
1. ```sudo apt-get install autoconf automake libtool curl make g++ unzip```
2. unzip the downloaded folder using ```unzip [.zip]```
3. enter in the unzipped directory (i. e. "protobuf-python-3.13.0", but by
   unzipping there could be another folder with the same name so get in it)
4. ```./configure```
5. ```make```
6. ```make check``` (not mandatory, but if you do that you would be sure
   that there wouldn't be problems)
7. ```sudo make install```
8. ``````

### pip3 protoc