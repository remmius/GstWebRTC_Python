Example-code gstwebrtc as callee or caller
==============

# Purpose
With GStreamer 1.14 release, a WebRTC-endpoint was introduced. As the provided examples in Python handle only outgoing calls from the application to a browser, here a example how to call your application from a browser.
Thought of usecase hereby is to call a device (e.g. Pi) at home, which has a camera attached, from my remote-browser (eg. smartphone) and to use it as securtiy-camera with audio-support. 

Currently does not work with the GStreamer 1.16.2!
# Usage

## Start signaling server
Excecute:
```
    npm start
```
Now go to "https://localhost:8443/Webrtc-demo" in your browser and
1. Choose which media you will share with your callee. By default currently all incoming media is accepted. Register at the webserver. 
2. Choose the client you want to call and call
3. Connection should get established

## Start python application
To start as a callee use:
```
python3 webrtc-sendrecv_calle_caller2.py <yourusername>
```
To start as a caller use:
```
python3 webrtc-sendrecv_calle_caller2.py <yourusername> --peerid <remote-id>
```
After a call has ended, the application automatically reconnects to the signalling server again and is thereby able to be recalled.

# Used devices
Currently the following setups have been involved in testing:
* Chrome and Firefox on Ubuntu 18.04
* Chrome and Firefox on Android 7.1
    * For my 4G-mobile-provider, it is neccessary to use a turn-server to establish a connection
* Python-application on Pi 2 Model B v1.1 with Raspbian Buster
    * The outgoing video on a Pi "requires" (well not technically but it makes sense to use the HW-encoder) to use the omxh264, therefore the second endpoint is required to support h264-codec (not the case on my mobile firefox ). Otherwise no common format will be found.
    * - [ ] Bi-dirctional video+audio communition does work, however it takes a long time to establish a connection (ssl-warnings TOFIX) and the displayed the video had poor quality (lag, decoder-framedrops) - TOFIX try with low remote resolution
* Python-application on Ubuntu 18.04
* TOFIX Promise of 'set-remote-description' does not seem to return. Python-application unresponsive...



# Setup

## Get a certificate
Either create a self-signed certificate by excecuting: 
```
./generate_cert.sh
```
Or create "recognised" certificate e.g. by following the guide in [Get a SSL-certificate for AWS-cloud](https://www.webcreta.com/how-to-letsencrypt-ssl-certificate-install-on-aws-ec2-ubuntu-instance/ "Named link title") 

## Setup signaling server
Install and start
```
sudo apt install npm
npm install
npm start
```
To access the server from outside, check your firewall settings for port 8443.
If you want to start the server on startup you can e.g. use pm2:
```
sudo npm install pm2 -g
cd gstreamer-browser-webrtc/
sudo pm2 start npm -- start
sudo pm2 save
```
## Setup Turn server
If you use 4G, you most likly will require a turn-server. I mainly followed myself [Setup turn server](https://medium.com/@omidborjian/setup-your-own-turn-stun-signal-relay-server-on-aws-ec2-78a8bfcb71c3 "Named link title").
Anyhow, in short here for an EC2-AWS-System:
Allow the following in your firewall/secuirtiy groups 
```
3478 : UDP
3478 : TCP
10100–10150 : UDP
```
Install e.g. coturn (or any other turn-server-app) and adapt the configuration to your needs:
```
sudo apt-get install coturn
sudo nano /etc/turnserver.conf
```
With e.g.:
```
realm=mine.com
fingerprint
external-ip=<ec2-public-ip-address>
listening-port=3478
min-port=10100
max-port=10150
log-file=/var/log/turnserver.log
verbose
user=<username>:<password> #don't expose this
#and some optional stuff for basic missue avoidance
channel-lifetime=600 #limits connection to 600sec
user-quota=5
total-quota=5
max-bps=1000000
```

The username:pw should be set in the WebRTC settings. Note: Obviously the username:pw have been changed in my turn-server.
Finally enable autostartup via:
```
sudo nano /etc/default/coturn
```
and set 
```
TURNSERVER_ENABLED=1
```
To test your turn-server, you can use https://webrtc.github.io/samples/src/content/peerconnection/trickle-ice/

Finally set the turn-server in:
* ./client/webrtc.js in "peerConnectionConfig" for the Browser
* ./client/gstwebrt_caller_calle.py in "self.webrtc.set_property("turn-server","turn://USER:PWD@IP:PORT")" for the python-application

# Helpful Links
* [WebRTC Information](https://temasys.io/webrtc-ice-sorcery/ "Named link title")
* [Setup turn server](https://medium.com/@omidborjian/setup-your-own-turn-stun-signal-relay-server-on-aws-ec2-78a8bfcb71c3 "Named link title") 
* [Get a SSL-certificate for AWS-cloud](https://www.webcreta.com/how-to-letsencrypt-ssl-certificate-install-on-aws-ec2-ubuntu-instance/ "Named link title") 

## Source and starting point  
* https://github.com/centricular/gstwebrtc-demos License: MIT, [gstwebrtc-demos Commit](https://github.com/centricular/gstwebrtc-demos/commit/0989b555414827aef1dc1cd811dee390bca740d3 "Named link title")
* https://github.com/shanet/WebRTC-Example License: BSD 2-Clause, [WebRTC-Example Commit](https://github.com/shanet/WebRTC-Example/commit/5f67119e4e3fe6911361a30aba7097143d3d3f6d "Named link title")

## License

The MIT License (MIT)

Copyright (c) 2014 Remmius

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
