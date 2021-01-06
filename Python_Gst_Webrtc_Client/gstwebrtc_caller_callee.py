#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Dec 22 11:38:18 2020
#GST_DEBUG=3 gst-launch-1.0 -v videotestsrc is-live=true ! video/x-raw,width=120,height=80 ! videoconvert ! omxh264enc ! capsfilter caps="video/x-h264,profile=(string)baseline"  ! rtph264pay name=videopay !  fakesink
GST_DEBUG=3 gst-launch-1.0 -v v4l2src device=/dev/video0 ! video/x-raw,width=120,height=80,framerate=30/1  ! videoconvert ! omxh264enc ! capsfilter caps="video/x-h264,profile=(string)baseline, level=(string)1" ! rtph264pay name=videopay ! fakesink
@author: klaus
"""
import nest_asyncio
nest_asyncio.apply() #required to run this programm in spyder
import PipelineBuilder
import jwt_token as jwt
import ssl
import websockets
import asyncio
import sys
import json
import argparse
import time
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
#gi.require_version('GstPbutils', '1.0')
#from gi.repository import GstPbutils
gi.require_version('GstWebRTC', '1.0')
from gi.repository import GstWebRTC
gi.require_version('GstSdp', '1.0')
from gi.repository import GstSdp

import logging as logger
logger.basicConfig(format='%(asctime)s %(message)s',level=logger.INFO)

DEFAULT_PIPELINE="realsrc_aud_vid"#'testsrc_aud_vid' #
DEFAULT_PIPELINE='testsrc_aud_vid' 
DEFAULT_DOMAIN='mydevcloud.freedynamicdns.org'
DEFAULT_APPNAME='/gstreamer-browser-webrtc'
HTTP_USER='user'
HTTP_PWD='test'
TURN_USER='user'
TURN_PWD='test'

DEFAULT_HTTP_SERVER="https://"+DEFAULT_DOMAIN+DEFAULT_APPNAME+"/logindata"
DEFAULT_WS_SERVER="wss://"+DEFAULT_DOMAIN+DEFAULT_APPNAME+"/webrtc-ws"
DEFAULT_STUN="stun://stun.l.google.com:19302"
DEFAULT_TURN="turn://"+TURN_USER+":"+TURN_PWD+"@"+DEFAULT_DOMAIN+":3478"

LOCAL_MEDIA_SUPPORT={"audio":"sendrecv","video":"sendrecv"}

#Example pipeline for real media input with audio-OPUS and video-H264-encoding
'''
webrtcbin name=webrtc
 pulsesrc ! audioconvert ! audioresample ! queue name=audiobase ! opusenc name=audioenc ! rtpopuspay name=audiopay pt=111 !
 capsfilter caps="application/x-rtp" ! queue name=audioqueue ! webrtc.sink_0
 autovideosrc ! video/x-raw,width=120,height=80 ! clockoverlay ! videoconvert ! queue name=videobase ! x264enc name=videoenc tune=zerolatency ! rtph264pay name=videopay ! 
 capsfilter caps="application/x-rtp,profile-level-id=(string)42c015" ! queue name=videoqueue ! webrtc.sink_1
'''

#Example pipeline for VP8-video-encoding
'''
webrtcbin name=webrtc 
 audiotestsrc is-live=true volume=0.1 wave=blue-noise ! audioconvert ! audioresample ! queue name=audiobase ! opusenc name=audioenc ! rtpopuspay name=audiopay pt=111 !
 queue name=audioqueue ! webrtc.sink_0
 videotestsrc is-live=true ! video/x-raw,width=120,height=80 ! clockoverlay ! videoconvert ! queue name=videobase ! vp8enc deadline=1 name=videoenc ! rtpvp8pay name=videopay !
 capsfilter caps="application/x-rtp" ! queue name=videoqueue ! webrtc.sink_1
'''

#Example pipeline for test-media input with audio-OPUS and video-H264-encoding
'''
webrtcbin name=webrtc 
 audiotestsrc is-live=true volume=0.1 wave=blue-noise ! audioconvert ! audioresample ! queue name=audiobase ! opusenc name=audioenc ! rtpopuspay name=audiopay pt=111 !
 capsfilter caps="application/x-rtp" ! queue name=audioqueue ! webrtc.sink_0
 videotestsrc is-live=true ! video/x-raw,width=120,height=80 ! clockoverlay ! videoconvert ! queue name=videobase ! x264enc name=videoenc tune=zerolatency ! rtph264pay name=videopay ! 
 capsfilter caps="application/x-rtp,profile-level-id=(string)42c015" ! queue name=videoqueue ! webrtc.sink_1
'''

GST_DIRECTIONS={"recvonly":GstWebRTC.WebRTCRTPTransceiverDirection.RECVONLY,
   "sendonly":GstWebRTC.WebRTCRTPTransceiverDirection.SENDONLY,
   "sendrecv":GstWebRTC.WebRTCRTPTransceiverDirection.SENDRECV,
   "inactive":GstWebRTC.WebRTCRTPTransceiverDirection.INACTIVE   #,"inactive","none" not yet working
   }

class WebRTCClient:
    def __init__(self, id_, peer_id, server,caller,pipeline):
        self.jwt_token=jwt.get_token(user=HTTP_USER,pwd=HTTP_PWD,url=DEFAULT_HTTP_SERVER,JWT_TAG="JWT_WS")        
        self.caller=caller
        self.id_ = id_
        self.conn = None
        self.peer_id = peer_id
        self.server = server    
        self.setup_pipeline(pipeline)
        
    def setup_pipeline(self,pipeline):
        self.pipebuilder=PipelineBuilder.PipelineBuilder(pipeline)    
        self.webrtc = self.pipebuilder.pipe.get_by_name('webrtc')
        
        bundle="max-bundle" #max-compat #"none" not working #"balanced" not implemented 
        print(Gst.version())
        if(Gst.version().minor>=16):
            self.webrtc.set_property("bundle-policy",bundle)  
        else:
            logger.warning("\n Bundle not available in gst {}.{}- consider using 1.16 gstreamer-version \n".format(Gst.version().major,Gst.version().minor))
        
        self.webrtc.set_property("turn-server",DEFAULT_TURN)
        self.webrtc.set_property("stun-server",DEFAULT_STUN)
        self.webrtc.connect('on-ice-candidate', self.send_ice_candidate_message)
        self.webrtc.connect('pad-added', self.on_incoming_stream)
        #only needed for caller                
        if (self.caller==True):
            for media_type in LOCAL_MEDIA_SUPPORT:
               self.setup_transreciever(media_type,self.pipebuilder.get_mediaprio())               
            self.webrtc.connect('on-negotiation-needed', self.on_negotiation_needed)
    
    def setup_transreciever(self,media_type,encoder_list):
            direction =GST_DIRECTIONS[LOCAL_MEDIA_SUPPORT[media_type]] #GstWebRTC.WebRTCRTPTransceiverDirection.SENDRECV
            caps0=None
            if(isinstance(encoder_list[media_type],str)):#typically to create an answer based on an offer 
                #only one codec available in this case
                caps0=self.pipebuilder.get_media()[encoder_list[media_type]]['caps']                  
            else:#typically create an sdp-offer with multiple codec-offers
                for encoder in encoder_list[media_type]:  
                    caps0=self.pipebuilder.generate_caps(media_type,encoder,caps0)
            print("add trans",caps0.to_string())       
            self.webrtc.emit('add-transceiver', direction, caps0)
        
    async def connect(self):
        sslctx = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
        self.conn = await websockets.connect(self.server, ssl=sslctx,extra_headers=[('Cookie', "JWT_WS="+self.jwt_token)])
        await self.conn.send('{"type":"HELLO","uuid":"%s"}' % self.id_)
        
    async def setup_call(self):
        await self.conn.send('{"type":"SESSION","peer_id":"%s"}' % self.peer_id)

    def get_sdp_direction(self,sdpmsg,media_type):
        for j in range(sdpmsg.medias_len()):#loop over offered media-streams/types
            media=sdpmsg.get_media(j)
            if(media_type == media.get_media()):
                for n in range(media.attributes_len()):
                    if(media.get_attribute(n).value=="" and media.get_attribute(n).key in GST_DIRECTIONS):
                        print(media.get_attribute(n).key)                    
                        return media.get_attribute(n).key       
    
    def check_direction_for_sending(self,sdpmsg,medium):
        remote_direction=self.get_sdp_direction(sdpmsg,medium)   
        if (remote_direction=='sendonly' or remote_direction=='inactive' or remote_direction=='none'):#remote does not accept our data
            return False        
        elif not ('send' in LOCAL_MEDIA_SUPPORT[medium]):# local does not want to send data
            return False
        else:
            return True
    
    def send_sdp(self, sdp,sdp_type):
        sdpmsg=sdp.sdp                     
        text = sdpmsg.as_text()
        print("send sdp-",sdp_type)
        print(text)
        msg = json.dumps({'sdp': {'type': sdp_type, 'sdp': text}})
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self.conn.send(msg))
        loop.close()
    
    def on_sdp_created(self, promise, _, sdp_type):
        ret = promise.wait()
        if ret != Gst.PromiseResult.REPLIED:
            logger.warning("prmoise did not reply")
            return
        reply = promise.get_reply()
        #sdp = reply.get_value(sdp_type)       
        sdp=reply[sdp_type]           
        if sdp:    
            promise = Gst.Promise.new()
            self.webrtc.emit('set-local-description', sdp, promise)   
            promise.interrupt()                             
            self.send_sdp(sdp,sdp_type)         
            
    def on_negotiation_needed(self, element):
        logger.info("on_negotiation_needed {}".format(element))
        promise = Gst.Promise.new_with_change_func(self.on_sdp_created, element, "offer")        
        element.emit('create-offer', None, promise)
            
    def send_ice_candidate_message(self, _, mlineindex, candidate):
        icemsg = json.dumps({'ice': {'candidate': candidate, 'sdpMLineIndex': mlineindex}})
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self.conn.send(icemsg))
        loop.close()

    def on_incoming_stream(self, _, pad):  
        logger.info("on stream in webrtc")   
        self.pipebuilder.add_decodebin(pad)
    
    def build_outgoing_pipelines(self,sdpmsg):
        for media_type in LOCAL_MEDIA_SUPPORT:
            if(self.check_direction_for_sending(sdpmsg,media_type)): #TODO not according to local-media-offer but according to answer        
                self.pipebuilder.build_outgoing_pipeline2(media_type)               
        
    async def handle_sdp(self, message):
        msg = json.loads(message)            
        if 'sdp' in msg:
            sdp = msg['sdp']
            print ('Received %s :' % sdp['type'] )
            if (sdp['type'] == 'answer'): 
                sdp = sdp['sdp']                
                res, sdpmsg = GstSdp.SDPMessage.new()
                GstSdp.sdp_message_parse_buffer(bytes(sdp.encode()), sdpmsg)
                answer = GstWebRTC.WebRTCSessionDescription.new(GstWebRTC.WebRTCSDPType.ANSWER, sdpmsg)
                print(sdpmsg.as_text())
                promise = Gst.Promise.new()
                self.webrtc.emit('set-remote-description', answer, promise)                
                promise.interrupt()
                for media_type in LOCAL_MEDIA_SUPPORT:
                    if(self.check_direction_for_sending(sdpmsg,media_type)):#TODO do not send-data if answer is sendonly
                        self.pipebuilder.check_sdp(sdpmsg,media_type,validate_caps=True,store_caps="none")
                self.build_outgoing_pipelines(sdpmsg)   
                
            elif (sdp['type'] == 'offer'):                
                sdp = sdp['sdp']
                res, sdpmsg = GstSdp.SDPMessage.new()
                GstSdp.sdp_message_parse_buffer(bytes(sdp.encode()), sdpmsg)                
                offer=GstWebRTC.WebRTCSessionDescription.new(GstWebRTC.WebRTCSDPType.OFFER,sdpmsg)   
                print(sdpmsg.as_text())
                #build pipeline   
                for media_type in LOCAL_MEDIA_SUPPORT:
                    if(self.check_direction_for_sending(sdpmsg,media_type)):#TODO do not send-data if offer is sendonly 
                        self.pipebuilder.check_sdp(sdpmsg,media_type,validate_caps=True,store_caps="input")
                        self.setup_transreciever(media_type,self.pipebuilder.get_webrtcmedia())
                    else:
                        logger.info("media {} has direction {}. Therefore no outgoing pipeline".format(media_type,LOCAL_MEDIA_SUPPORT[media_type]))
                        # inactive or recvonly - no need for outgoing pipeline 
                        pass
                                    
                self.pipebuilder.start_pipeline()
                promise = Gst.Promise.new()
                self.webrtc.emit('set-remote-description', offer, promise)           
                promise.wait()
                
                logger.info("start create answer")
                promise = Gst.Promise.new_with_change_func(self.on_sdp_created, self.webrtc, "answer")
                self.webrtc.emit('create-answer', None, promise)
                logger.info("waiting for create answer promise")
                #build outgoing pipeline
                self.build_outgoing_pipelines(sdpmsg)
                    #Note:now there are 2-4 transrecievers in the webrtc-element depending on the number of outgoing media
                        #however negotiation took place already and therefore it does not matter
                        #pipeline-build always sets up transrecievers with SENDRECV-direction..
                        #in python gst 1.16 the direction is not writable at the moment..it seems 
                        
        elif 'ice' in msg:
            ice = msg['ice']
            candidate = ice['candidate']
            sdpmlineindex = ice['sdpMLineIndex']
            self.webrtc.emit('add-ice-candidate', sdpmlineindex, candidate)
        
        elif ('type' in msg):
            if msg['type']=="EXIT":          
                self.pipebuilder.stop_pipeline()
                return -1
        return 0        
        
    async def loop(self):
        result=0        
        assert self.conn  
        async for message in self.conn:  
            if message == 'HELLO':
                if self.caller==True:    
                    await self.setup_call()
                else:
                    print("Hello. Waiting to be called")
                    
            elif message == 'SESSION_OK':
                if self.caller==True:     
                    self.pipebuilder.start_pipeline()
                print("session ok")
                
            elif message.startswith('ERROR'):
                print (message)
                result=1
                break
            elif message.startswith('{"peers"'):
                msg = json.loads(message)
                print("Update of peer list",msg['peers'])
            else:
                res=await self.handle_sdp(message)
                if (res==-1):
                    result=0
                    break
        msg = json.dumps({"type":"EXIT","uuid":self.id_ })
        await self.conn.send(msg)
        return result

def check_plugins():
    needed = ["opus", "vpx","nice", "webrtc", "dtls", "srtp", "rtp",
              "rtpmanager", "videotestsrc", "audiotestsrc","omx","x264"]#
    missing = list(filter(lambda p: Gst.Registry.get().find_plugin(p) is None, needed)) 
    #if omxh264 is not supported, try to use x264enc
    if("omx" in missing):
        if not("x264" in missing):
            PipelineBuilder.MEDIA["H264"]['encoder']="x264enc"
            missing.remove('omx')   
            logger.warning("Missing omx-plugin. But x264enc is available")
    if len(missing):
        logger.warning('Missing gstreamer plugins:', missing)
        return False
    return True

if __name__=='__main__':
    Gst.init(None)    
    if not check_plugins():
        sys.exit(1)

    parser = argparse.ArgumentParser()
    parser.add_argument('myid', help="Your peer-id as a string")
    parser.add_argument('--peerid', help='String ID of the peer to call. If not given programm acts as a calle')
    parser.add_argument('--server', help='Signalling server to connect to. Default: "wss://127.0.0.1:8443"',default=DEFAULT_WS_SERVER)
    parser.add_argument('--audio',choices=list(GST_DIRECTIONS.keys()), help='Set webrtc-direction of audio.',default='sendrecv')
    parser.add_argument('--video',choices=list(GST_DIRECTIONS.keys()), help='Set webrtc-direction of audio.',default='sendrecv')
    #parser.add_argument('--pipeline',choices=list(PIPELINES.keys()), help='gstreamer pipeline to use. Default {}'.format(DEFAULT_PIPELINE),default=DEFAULT_PIPELINE)

    args = parser.parse_args()    
    if(args.peerid==None):
        caller=0
    else:
        caller=1   
    if not(args.audio==None):
        LOCAL_MEDIA_SUPPORT["audio"]=args.audio
    if not(args.audio==None):
        LOCAL_MEDIA_SUPPORT["video"]=args.video 
    
    print("registering with ID:", args.myid)
    print("registering to call peerid:", args.peerid)
    #args.server='wss://webrtc.nirbheek.in:8443'
    while True:  
            c = WebRTCClient(args.myid, args.peerid, args.server,caller,"")
            asyncio.get_event_loop().run_until_complete(c.connect())            
            result=asyncio.get_event_loop().run_until_complete(c.loop())
            # TODO: notfiy partner peer      
            print("stopped call/pipeline")
            if(result==1):
                time.sleep(5)
