# Handcart - Fenice
This is the repo for Fenice's handcart.

## Index
- [Structure](#structure)
- [Setup](#setup)
- [Installation](#installation)
- [Usage](#usage)
- [Compiling](#compiling)

## Structure
![General diagram](https://app.lucidchart.com/publicSegments/view/5d5eb5a3-77bc-44d1-b641-f867606ba91e/image.jpeg)

![Communication diagram](https://lucid.app/publicSegments/view/ad0abc76-47aa-48bb-9229-563d7b6c2a0f/image.jpeg)

### Diagram links
https://app.lucidchart.com/invitations/accept/7fbd23c5-16c0-4441-8aa8-d0963f368066

https://lucid.app/invitations/accept/653e7b85-554d-4b44-bffd-f446f46eb0ba


# Setup

### Using Ubuntu 20.4

- Python 3.8
- pip3 20.2.3
- protoc 3.13.0
- pip3 protobuf 3.13.0
- pip3 grpcio 1.32.0

> WARNING: After [installation](#installation), if the pip protobuf and the
> protoc version are different (usually pip is the older one) you have to
> update it by `pip install --upgrade protobuf`
> (check versions using `pip3 show protobuf` and `protoc --version`).

## Installation

### Python 3
    sudo apt-get install python3.8

### pip3
    sudo apt-get install python3-pip
    
If you already had installed pip it could be necessary to update it using

    python3 -m pip install --upgrade pip

### Protocol Buffer (protoc)
Download the python `.zip` at
[this link](https://github.com/protocolbuffers/protobuf/releases),
then run the following commands:
1. `sudo apt-get install autoconf automake libtool curl make g++ unzip` to install
   tools needed to install protoc
2. unzip the downloaded folder using `unzip [.zip]`
3. enter in the unzipped directory (i. e. "protobuf-python-3.13.0", but by
   unzipping there could be another folder with the same name so get in it)
4. `./configure`
5. `make`
6. `make check` (not mandatory, but if you do that you would be sure
   that there wouldn't be problems)
7. `sudo make install`
8. `sudo ldconfig` (it refresh the shared library cache)
9. Just to clean up you can run `make clean`

> **Hint on install location:**<br>
> By default, the package will be installed to `/usr/local`.  However,
> on many platforms, `/usr/local/lib` is not part of `LD_LIBRARY_PATH`.
> You can add it, but it may be easier to just install to `/usr` instead.
> To do this, invoke `./configure` as follows:
>
>     ./configure --prefix=/usr

**More details about the whole installation in the `./src/README.md` file.**

### pip3 protoc
Check it is already installed. If not, just run this:
    
    sudo pip install protobuf
    
If it is already installed check the `WARNING` [up here](#using-ubuntu-20.4).

### gRPC
    python3 -m pip install grpcio
    
### gRPC tools
    python3 -m pip install grpcio-tools
    
### Examples
If you need them, there are some examples in the
[owner repository](https://github.com/grpc/grpc) that you can clone using
    
    git clone -b v1.32.0 https://github.com/grpc/grpc

## Compiling
To compile the `.proto` and get the `.py` file that describes the `.proto` run

    protoc [FILE_NAME.proto] --python-out=[OUTPUT_FOLDER]

If you need to create a service you need to use another command to compile the proto,
so you'll get both the `[FILE_NAME]_pb2.py` and the `[FILE_NAME]_pb2_grpc.py`:

    python3 -m grpc_tools.protoc -I[WHERE_THE_FILE_IS] --python_out=[WHERE_YOU_WANT_TO_HAVE_THE_PY_OUTPUT] --grpc_python_out=[WHERE_YOU_WANT_TO_HAVE_THE_GRPC_PY_OUTPUT] [FILE_NAME.proto]
    
> **Example:**
>
>     python3 -m grpc_tools.protoc -I./ --python_out=./ --grpc_python_out=./ ./messages.proto
>
> Where `./` is the current folder and `message.proto` the file that I would
> convert to `.py`.
> 2 files will be created: `messages_pb2.py` and `message_pb2_grpc.py`.<br>
> The compiler should show a `warning`, but the `_grpc_.py` file should have been
> created as you need it.
>
> You can find these files in the `./communication` folder.

## Usage



## Sources
- [ProtocolBuffer](https://developers.google.com/protocol-buffers)
- [gRPC](https://grpc.io/)

#backend
- [here](https://www.brusa.biz/_files/drive/02_Energy/Chargers/NLG5/NLG5_BRUSA.html) you can find BRUSA's CAN messages
- For pork's can messages search on other E-Agle repo