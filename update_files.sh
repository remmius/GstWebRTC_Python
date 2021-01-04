#!/bin/bash
HOST_DNS='mydevcloud.freedynamicdns.org'
APP_NAME='/gstreamer-browser-webrtc'
JWT_SECRET='usertest'
HTTP_USER='user'
HTTP_PWD='test'
EXT_IP=35.204.54.229
INT_IP=10.164.0.2
TURN_USER='user'
TURN_PWD='test'

#docker-env-file for signaling-server
echo -e "HOST_DNS=$HOST_DNS \nAPP_NAME=$APP_NAME \nJWT_SECRET=$JWT_SECRET \n" > ./server/signalling_server.env

#update static files: for now do per file instead of updating the whole directory...
sed -i "s+/gstreamer-browser-webrtc+$APP_NAME+g" ./server/backend-server/client/login.html
sed -i "s+/gstreamer-browser-webrtc+$APP_NAME+g" ./server/backend-server/client/index.html

sed -i "s+/mydevcloud.freedynamicdns.org+$HOST_DNS+g" ./server/backend-server/client/webrtc.js
sed -i "s+/gstreamer-browser-webrtc+$APP_NAME+g" ./server/backend-server/client/webrtc.js
sed -i "s+credential:'test'+credential:'$TURN_PWD'+g" ./server/backend-server/client/webrtc.js
sed -i "s+username:'user'+username:'$TURN_USER'+g" ./server/backend-server/client/webrtc.js

sed -i "s+/mydevcloud.freedynamicdns.org+$HOST_DNS+g" ./server/coturn/turnserver.conf
sed -i "s+user=user:test+user=$TURN_USER:$TURN_PWD+g" ./server/coturn/turnserver.conf
sed -i "s+external-ip=35.204.54.229/10.164.0.2+external-ip=$EXT_IP/$INT_IP+g" ./server/coturn/turnserver.conf

sed -i "s+mydevcloud.freedynamicdns.org+$HOST_DNS+g" ./server/nginx/default
sed -i "s+/gstreamer-browser-webrtc+$APP_NAME+g" ./server/nginx/default

sed -i "s+/mydevcloud.freedynamicdns.org+$HOST_DNS+g" ./Python_Gst_Webrtc_Client/gstwebrtc_caller_callee.py
sed -i "s+/gstreamer-browser-webrtc+$APP_NAME+g" ./Python_Gst_Webrtc_Client/gstwebrtc_caller_callee.py
sed -i "s+HTTP_USER='user'+HTTP_USER='$HTTP_USER'+g" ./Python_Gst_Webrtc_Client/gstwebrtc_caller_callee.py
sed -i "s+HTTP_PWD='user'+HTTP_PWD='$HTTP_PWD'+g" ./Python_Gst_Webrtc_Client/gstwebrtc_caller_callee.py
sed -i "s+TURN_USER='user'+TURN_USER='$TURN_USER'+g" ./Python_Gst_Webrtc_Client/gstwebrtc_caller_callee.py
sed -i "s+TURN_PWD='user'+TURN_PWD='$TURN_PWD'+g" ./Python_Gst_Webrtc_Client/gstwebrtc_caller_callee.py

sed -i "s+/mydevcloud.freedynamicdns.org+$HOST_DNS+g" ./Python_Gst_Webrtc_Client/jwt_token.py
sed -i "s+/gstreamer-browser-webrtc+$APP_NAME+g" ./Python_Gst_Webrtc_Client/jwt_token.py
sed -i "s+HTTP_USER='user'+HTTP_USER='$HTTP_USER'+g" ./Python_Gst_Webrtc_Client/jwt_token.py
sed -i "s+HTTP_PWD='user'+HTTP_PWD='$HTTP_PWD'+g" ./Python_Gst_Webrtc_Client/jwt_token.py
