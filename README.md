Example-code gstwebrtc as callee or caller
==============

# Purpose
With GStreamer 1.14 release (this example requires 1.16+), a WebRTC-endpoint was introduced. As the provided examples in Python handle only outgoing calls from the application to a browser. Here is a more flexible example allowing to act as a callee and offer different encodings in the gst-offer. 
Moreover there is a possibility to limit the media-direction of the gstwebrtc-client, e.g. to act as a one-way video/audio-streaming solution ("sendonly"-mode).
Thought of usecase hereby is to call a device (e.g. Pi) at home, which has a camera attached, from my remote-browser (eg. smartphone) and to use it as securtiy-camera with audio-support. 

# Usage
Adapt settings in the update_files.sh and overwrite the changes in the files. 
```
    ./update_files.sh
```
Note: This simply overwriting the default setting- this does therefore only works once so far. Also assumes the certificates to be created with Let’s Encrypt TO FIX

## Start signaling server and Turn-server
Excecute:
```
    cd <repo-base>/server
    docker-compose up -d
```
Now go to "https://localhost:8443/webrtc" in your browser and
1. Choose which media you will share with your callee. By default currently all incoming media is accepted. Register at the webserver. 
2. Choose the client you want to call and call
3. Connection should get established

## Start python application
To start as a callee use:
```
python3 gstwebrtc_caller_callee.py <yourusername>
```
To start as a caller use:
```
python3 gstwebrtc_caller_callee.py <yourusername> --peerid <remote-id>
```
After a call has ended, the application automatically reconnects to the signalling server again and is thereby able to be recalled.
To limit the media driection of the client, use the option --audio and --video. Note currently not all combinations are working with the browser resp. with another gst-client..

### Start python application with docker
Run
```
docker run -it --rm --net=host pygstwebrtc 134 # xserver only support
```
To test with the docker-setup, best is to use "sendonly"-media support in the docker-client to avoid problems with audio/xserver-access.
Example command with audio+x-server support for my host system (ubuntu 18.04)
```
docker run -it -v /tmp/.X11-unix:/tmp/.X11-unix -e DISPLAY=unix$DISPLAY --rm --net=host --device /dev/snd -e PULSE_SERVER=unix:${XDG_RUNTIME_DIR}/pulse/native -v ${XDG_RUNTIME_DIR}/pulse/native:${XDG_RUNTIME_DIR}/pulse/native -v ~/.config/pulse/cookie:/root/.config/pulse/cookie --group-add $(getent group audio | cut -d: -f3) pygstwebrtc 134

``` 

With raspian-os set export OPENSSL_CONF="" to avoid dtls-errors. See: https://gitlab.freedesktop.org/gstreamer/gst-plugins-bad/-/issues/811

# Used/"Tested" devices
Currently the following setups have been involved in testing:
* Chrome and Firefox on Ubuntu 18.04
* Chrome and Firefox on Android 7.1
    * For my 4G-mobile-provider, it is neccessary to use a turn-server to establish a connection
* Python-application on Pi 2 Model B v1.1 with Raspbian Buster
    * The outgoing video on a Pi "requires" (well not technically but it makes sense to use the HW-encoder) to use the omxh264, therefore the second endpoint is required to support h264-codec (not the case on my mobile firefox ). Otherwise no common format will be found.
    * - [ ] Bi-dirctional video+audio communition does work, however it takes a long time to establish a connection (ssl-warnings TOFIX) and the displayed the video had poor quality (lag, decoder-framedrops) - TOFIX try with low remote resolution
* Python-application on Ubuntu 20.04 with gstreamer 1.16.2 and 20.10 1.18.0. The version gst-1.14 does not work reliable with this code.
## TO DO
* Fix error for some combinations of limited media-support between gst-webrtc and browser/gst-webrtc
* Improve supported codec-detection (esp. omxh264 and xh264,vp8,vp9) on sdp-offer
* To Do: 
    * Proper update of files
    * Add configuration for video-resolution
    * Add more audio-codecs 
    * Webclient: sometimes registering does not work, remove old id when reconnecting, properly update default value for peerid on mobile-devices
    
# Setup-application 
## On host
Install the required packages to your host-system
```
apt install -y alsa-base alsa-utils python3 python3-pip python3-gst-1.0 gstreamer1.0-tools gstreamer1.0-nice gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-plugins-good libgstreamer1.0-dev git libglib2.0-dev libgstreamer-plugins-bad1.0-dev libsoup2.4-dev libjson-glib-dev gstreamer1.0-alsa gstreamer1.0-pulseaudio
```
```
pip3 install requests websockets nest_asyncio
```
## With docker:
Build the dockerfile:
```
cd <repo-base>/Python_Gst_Webrtc_Client/
docker build --tag pygstwebrtc .
xhost local:docker #give permission for xServer if required
```

# Setup-Server

## Get a certificate
Either create a self-signed certificate by excecuting: 
```
./generate_cert.sh
```
Or create "recognised" certificate e.g. by following the guide in [Get a SSL-certificate for AWS-cloud](https://www.webcreta.com/how-to-letsencrypt-ssl-certificate-install-on-aws-ec2-ubuntu-instance/ "Named link title") 

## Setup signaling server
Install docker and docker-compose and run
```
docker-compose up -d
```
To access the server from outside, check your firewall settings for port 8443.

## Setup Turn server
If you use 4G, you most likly will require a turn-server. This is started automatically with docker-compose. 
Allow the following in your firewall/security groups 
```
3478 : UDP
3478 : TCP
10100–10150 : UDP
```
Adapt the configuration to your needs:
```
<repo-base>/server/coturn/turnserver.conf
```
With e.g.: (see coturn/turnserver.conf)
The username:pw should be set in the WebRTC settings. Note: Obviously the username:pw have been changed in my turn-server.

To test your turn-server, you can use https://webrtc.github.io/samples/src/content/peerconnection/trickle-ice/

# Helpful Links
* [WebRTC Information](https://temasys.io/webrtc-ice-sorcery/ "Named link title")
* [Setup turn server](https://medium.com/@omidborjian/setup-your-own-turn-stun-signal-relay-server-on-aws-ec2-78a8bfcb71c3 "Named link title") 
* [Get a SSL-certificate for AWS-cloud](https://www.webcreta.com/how-to-letsencrypt-ssl-certificate-install-on-aws-ec2-ubuntu-instance/ "Named link title") 

## Source and starting point  
* https://github.com/centricular/gstwebrtc-demos License: MIT, [Commit](https://github.com/centricular/gstwebrtc-demos/commit/0989b555414827aef1dc1cd811dee390bca740d3 "Named link title")
* https://github.com/shanet/WebRTC-Example License: BSD 2-Clause, [Commit](https://github.com/shanet/WebRTC-Example/commit/5f67119e4e3fe6911361a30aba7097143d3d3f6d "Named link title")

## License

The MIT License (MIT)

Copyright (c) 2020 Remmius

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
