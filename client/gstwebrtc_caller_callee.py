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
gi.require_version('GstWebRTC', '1.0')
from gi.repository import GstWebRTC
gi.require_version('GstSdp', '1.0')
from gi.repository import GstSdp

PIPELINES=dict()

PIPELINE_DESC = '''
webrtcbin name=sendrecv bundle-policy=max-bundle 
 pulsesrc ! audioconvert ! audioresample ! queue ! opusenc ! name=opuspay !
 queue name=audioqueue ! sendrecv.sink_0
 autovideosrc ! video/x-raw,width=320,height=240 ! videoconvert ! queue ! vp8enc deadline=1 name=videoenc ! rtpvp8pay name=videopay !
 queue name=videoqueue ! sendrecv.sink_1
'''
PIPELINES['realsrc_aud_vid']=PIPELINE_DESC

PIPELINE_DESC = '''
webrtcbin name=sendrecv bundle-policy=max-bundle 
 audiotestsrc is-live=true volume=0.1 wave=blue-noise ! audioconvert ! audioresample ! queue ! opusenc name=audioenc ! rtpopuspay name=audiopay !
 queue name=audioqueue ! sendrecv.sink_0
 videotestsrc is-live=true ! video/x-raw,width=120,height=80 ! clockoverlay ! videoconvert ! queue ! vp8enc deadline=1 name=videoenc ! rtpvp8pay name=videopay !
 queue name=videoqueue ! sendrecv.sink_1
'''
PIPELINES['testsrc_aud_vid']=PIPELINE_DESC

MEDIA={
        "H264":{"medium":"video","prio":3,"encoder":"omxh264enc","payloader":"rtph264pay","offered":False},
        "VP8":{"medium":"video","prio":1,"encoder":"vp8enc","payloader":"rtpvp8pay","offered":False},
        "VP9":{"medium":"video","prio":0,"encoder":"vp9enc","payloader":"rtpvp9pay","offered":False},
        "OPUS":{"medium":"audio","prio":2,"encoder":"opusenc","payloader":"rtpopuspay","offered":False},
        }


class WebRTCClient:
    def __init__(self, id_, peer_id, server,caller,pipeline):
        self.pipeline=pipeline
        self.caller=caller
        self.id_ = id_
        self.conn = None
        self.pipe = None
        self.webrtc = None
        self.peer_id = peer_id
        self.server = server    
        
        self.MEDIA=MEDIA        
        self.pipe_info={"audio":{"sink_id":-1,"encoder":"OPUS"},
                        "video":{"sink_id":-1,"encoder":"H264"},
                        }
        
        #setup pipeline        
        self.pipe = Gst.parse_launch(self.pipeline)
        self.webrtc = self.pipe.get_by_name('sendrecv')
        
        #only needed for caller
        if (self.caller==True):
            self.webrtc.connect('on-negotiation-needed', self.on_negotiation_needed)
            
        self.webrtc.set_property("turn-server","turn://USER:PWD@10.192.255.65:3478")
        self.webrtc.set_property("stun-server","stun://stun.l.google.com:19302")
        self.webrtc.connect('on-ice-candidate', self.send_ice_candidate_message)
        self.webrtc.connect('pad-added', self.on_incoming_stream)

    async def connect(self):
        sslctx = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
        self.conn = await websockets.connect(self.server, ssl=sslctx)
        await self.conn.send('{"type":"HELLO","uuid":"%s"}' % self.id_)
        
    async def setup_call(self):
        await self.conn.send('{"type":"SESSION","peer_id":"%s"}' % self.peer_id)

    def send_sdp(self, sdp_msg,sdp_type):
        text = sdp_msg.sdp.as_text()
        print ('Sending %s :\n%s' % (sdp_type,text))
        msg = json.dumps({'sdp': {'type': sdp_type, 'sdp': text}})
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self.conn.send(msg))
               
    def on_sdp_created(self, promise, _, sdp_type):
        ret = promise.wait()
        if ret != Gst.PromiseResult.REPLIED:
            return
        reply = promise.get_reply()
        sdp = reply.get_value(sdp_type)                
        if sdp:
            promise = Gst.Promise.new()
            self.webrtc.emit('set-local-description', sdp, promise)            
            promise.interrupt()  
            self.send_sdp(sdp,sdp_type)
        
    def on_negotiation_needed(self, element):
        print("on_negotiation_needed",element)
        promise = Gst.Promise.new_with_change_func(self.on_sdp_created, self.webrtc, "offer")        
        element.emit('create-offer', None, promise)
        print("requested 'create-offer'")
            
    def send_ice_candidate_message(self, _, mlineindex, candidate):
        icemsg = json.dumps({'ice': {'candidate': candidate, 'sdpMLineIndex': mlineindex}})
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self.conn.send(icemsg))

    def on_incoming_decodebin_stream(self, _, pad):
        if not pad.has_current_caps():
            print (pad, 'has no caps, ignoring')
            return
        #Gst.init(None)
        caps = pad.get_current_caps()
        name = caps.to_string()
        print("capsname",name)
        if name.startswith('video'):
            q = Gst.ElementFactory.make('queue')
            conv = Gst.ElementFactory.make('videoconvert')           
            sink = Gst.ElementFactory.make('ximagesink')
            self.pipe.add(q)
            self.pipe.add(conv)
            self.pipe.add(sink)
            self.pipe.sync_children_states()
            
            pad.link(q.get_static_pad('sink'))
            q.link(conv)
            conv.link(sink)           
            
        elif name.startswith('audio'):
            q = Gst.ElementFactory.make('queue')
            conv = Gst.ElementFactory.make('audioconvert')
            resample = Gst.ElementFactory.make('audioresample')
            sink = Gst.ElementFactory.make('autoaudiosink')         
            self.pipe.add(q)
            self.pipe.add(conv)
            self.pipe.add(resample)
            self.pipe.add(sink)
            self.pipe.sync_children_states()            
                        
            pad.link(q.get_static_pad('sink'))
            q.link(conv)
            conv.link(resample)
            resample.link(sink)

    def on_incoming_stream(self, _, pad):  
        print("on_incoming_stream :")      
        if pad.direction != Gst.PadDirection.SRC:
            return        
        decodebin = Gst.ElementFactory.make('decodebin')
        decodebin.connect('pad-added', self.on_incoming_decodebin_stream)
        self.pipe.add(decodebin)
        decodebin.sync_state_with_parent()
        self.webrtc.link(decodebin)
    
    def start_pipeline(self):
        self.pipe.set_state(Gst.State.PLAYING)
        
    def stop_pipeline(self):
        self.pipe.set_state(Gst.State.NULL)        
        self.MEDIA=MEDIA
    
    def determine_sdp_media_setup(self,sdpmsg):        
        for j in range(sdpmsg.medias_len()):#loop over offered media-streams/types
            media=sdpmsg.get_media(j)
            #print("media-type:",media.get_media())
            self.pipe_info[media.get_media()]['sink_id']=j
            self.get_media_candidates(media)
            
        self.get_encoder(media_type="audio")
        self.get_encoder(media_type="video")
        
    def get_media_candidates(self,media):
        for k in range(media.formats_len()):                                                        
            caps=media.get_caps_from_media(int(media.get_format(k)))            
            for m in range (caps.get_size()):
                cap_struc=caps.get_structure(m)
                encoder_name=cap_struc.get_value("encoding-name") 
                if (encoder_name in self.MEDIA):
                    if(self.MEDIA[encoder_name]['offered']==False):
                        #For now we take the first payload per codex
                        self.MEDIA[encoder_name]['offered']=True                        
                        self.MEDIA[encoder_name]['pt']=cap_struc.get_value("payload")
                        #print("media-candidate: \n",caps.to_string())
    
    def get_encoder(self,media_type):
        #get the encoder with highest prio, which was offered in sdp
       #sort self.MEDIA by prio 
       for key, value in sorted(self.MEDIA.items(), key=lambda item: item[1]['prio'],reverse=True):
           #print("encoder: ", key," value: ",value)
           if(value['offered']==True and value['medium']==media_type):  
              self.pipe_info[media_type]['encoder']=key #self.MEDIA[key]["encoder"]
              break;
       print("outgoing media for {} is: {} with payload {}".format(media_type,self.pipe_info[media_type]['encoder'],self.MEDIA[key]["pt"]))

    def build_outgoing_pipeline(self,media_type):         
        #unlink/remove old pipeline from webrtc to encoder of raw data
        #build up new pipeline with correct enc+payload
        #link to correct webrtc-sink        
        if(self.pipe_info[media_type]['sink_id']>=0 and self.pipe_info[media_type]['sink_id']<2):       
            queue=self.pipe.get_by_name(media_type+"queue")        
            queue.unlink(self.webrtc)
            sinkpad=queue.sinkpads[0]
    
            element_list=list()
            element_list.append(queue)
            #delete all elements including encoder
            while(1):
                #unlink
                if(sinkpad.is_linked()):
                    src_pad=sinkpad.get_peer()
                    src_pad.unlink(sinkpad)
                #remove element
                parent_src_pad=src_pad.parent
                sinkpad=parent_src_pad.sinkpads[0] #sinkpad of next element in pipeline
                element_list.append(parent_src_pad)
                if('enc' in parent_src_pad.name):
                    if(sinkpad.is_linked()):
                        src_pad=sinkpad.get_peer()
                        src_pad.unlink(sinkpad)
                    last_pipeline_elm=src_pad.parent # videoconverter-elm
                    #delete all parent elemnts
                    for element in element_list:
                        #print("remove",element.name)
                        self.pipe.remove(element)                        
                        element.unparent()
                        element.set_state(Gst.State.NULL)                        
                        element=None
                    break;
            
            # re-build pipeline
            encoder_name=self.pipe_info[media_type]['encoder']                    
            enc = Gst.ElementFactory.make(self.MEDIA[encoder_name]['encoder'],media_type+"enc")
            if(media_type=="video" and self.MEDIA[encoder_name]['encoder']=="omxh264enc"):
                caps = Gst.Caps.from_string("video/x-h264,profile=baseline")     
                capsfilter = Gst.ElementFactory.make("capsfilter", "filter")
                capsfilter.set_property("caps", caps) 
                self.pipe.add(capsfilter)
                print("caps",capsfilter.get_property("caps").to_string() )
            
            payloader=Gst.ElementFactory.make(self.MEDIA[encoder_name]['payloader'],media_type+"pay")
            payloader.set_property("pt",self.MEDIA[encoder_name]['pt'])
            q=Gst.ElementFactory.make("queue",media_type+"queue")       
            self.pipe.add(q)
            self.pipe.add(payloader)
            self.pipe.add(enc)
            self.pipe.sync_children_states()
            last_pipeline_elm.link(enc)
            if(media_type=="video" and self.MEDIA[encoder_name]['encoder']=="omxh264enc"):
                enc.link(capsfilter)
                capsfilter.link(payloader)
            else:            
                enc.link(payloader)
            payloader.link(q)
            
            enc.sync_state_with_parent()  
            if(media_type=="video" and self.MEDIA[encoder_name]['encoder']=="omxh264enc"):
                capsfilter.sync_state_with_parent()
            payloader.sync_state_with_parent()
            q.sync_state_with_parent()
            #print(self.pipe.numchildren)
            #get the correct port to link the pipline too
            soll_sink_name="sink_"+str(self.pipe_info[media_type]['sink_id'])
             
            for sinkpad in self.webrtc.sinkpads:
                if sinkpad.name==soll_sink_name:
                    if(sinkpad.is_linked()):
                    #the target sink-pad of webrtc has not been unlinked yet, as it was wrongly connected by default pipeline
                        src_pad=sinkpad.get_peer()
                        src_pad.unlink(sinkpad)
                    break
       
            q.srcpads[0].link(sinkpad)
            print("set caps \n")
            print(media_type)
            print(self.MEDIA[encoder_name]['encoder'])
            #set caps video/x-h264,profile=baseline
            
                  
                
            
            
    async def handle_sdp(self, message):
        msg = json.loads(message)            
        if 'sdp' in msg:
            sdp = msg['sdp']
            if (sdp['type'] == 'answer'):
                assert(sdp['type'] == 'answer')
                sdp = sdp['sdp']
                print ('Received answer:\n%s' % sdp)
                res, sdpmsg = GstSdp.SDPMessage.new()
                GstSdp.sdp_message_parse_buffer(bytes(sdp.encode()), sdpmsg)
                answer = GstWebRTC.WebRTCSessionDescription.new(GstWebRTC.WebRTCSDPType.ANSWER, sdpmsg)
                promise = Gst.Promise.new()
                self.webrtc.emit('set-remote-description', answer, promise)
                promise.interrupt()
            elif (sdp['type'] == 'offer'):                
                sdp = sdp['sdp']
                print ('Received offer:\n%s' % sdp)                                
                
                #set remote-description
                res, sdpmsg = GstSdp.SDPMessage.new()
                GstSdp.sdp_message_parse_buffer(bytes(sdp.encode()), sdpmsg)
                offer=GstWebRTC.WebRTCSessionDescription.new(GstWebRTC.WebRTCSDPType.OFFER,sdpmsg)                
                promise = Gst.Promise.new()
                self.webrtc.emit('set-remote-description', offer, promise)              
                promise.wait()
                    
                
                self.determine_sdp_media_setup(sdpmsg) 
                #rebuild pipeline
                self.build_outgoing_pipeline(media_type="audio")    
                self.build_outgoing_pipeline(media_type="video")                          
                                        
                #start pipeline and request to create answer             
                self.start_pipeline()  
                promise = Gst.Promise.new_with_change_func(self.on_sdp_created, self.webrtc, "answer")
                self.webrtc.emit('create-answer', None, promise)
                
        elif 'ice' in msg:
            ice = msg['ice']
            candidate = ice['candidate']
            sdpmlineindex = ice['sdpMLineIndex']
            self.webrtc.emit('add-ice-candidate', sdpmlineindex, candidate)
        
        elif ('type' in msg):
            if msg['type']=="EXIT":          
                self.stop_pipeline()
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
                    self.start_pipeline()
                print("session ok")
                
            elif message.startswith('ERROR'):
                print (message)
                result=1
                break
            else:
                res=await self.handle_sdp(message)
                if (res==-1):
                    result=0
                    break
        msg = json.dumps({"type":"EXIT","uuid":self.id_ })
        await self.conn.send(msg)
        return result

def check_plugins():
    needed = ["opus", "vpx", "nice", "webrtc", "dtls", "srtp", "rtp",
              "rtpmanager", "videotestsrc", "audiotestsrc","omx","x264"]
    missing = list(filter(lambda p: Gst.Registry.get().find_plugin(p) is None, needed))
    print(missing)
    #if omxh264 is not supported, try to use x264enc
    if("omxh264enc" in missing):
        if not("x264" in missing):
            MEDIA["H264"]['encoder']="x264enc"
            missing.remove('omxh264enc')             
    print(MEDIA)
    if len(missing):
        print('Missing gstreamer plugins:', missing)
        return False
    return True

if __name__=='__main__':
    Gst.init(None)    
    if not check_plugins():
        sys.exit(1)
    default_pipeline='testsrc_aud_vid'
    parser = argparse.ArgumentParser()
    parser.add_argument('myid', help="Your peer-id as a string")
    parser.add_argument('--peerid', help='String ID of the peer to call. If not given programm acts as a calle')
    parser.add_argument('--server', help='Signalling server to connect to. eg "wss://127.0.0.1:8443"',default='wss://127.0.0.1:8443')
    parser.add_argument('--pipeline',choices=list(PIPELINES.keys()), help='gstreamer pipeline to use. Default {}'.format(default_pipeline),default=default_pipeline)

    args = parser.parse_args()    
    if(args.peerid==None):
        caller=0
    else:
        caller=1   
    print(args)
    if(1):
        while True:  
            c = WebRTCClient(args.myid, args.peerid, args.server,caller,PIPELINES[args.pipeline])
            asyncio.get_event_loop().run_until_complete(c.connect())            
            result=asyncio.get_event_loop().run_until_complete(c.loop())
            #notfiy partner peer
            # TODO:      
            print("stopped call/pipeline")
            if(result==1):
                time.sleep(5)

    
    
    

    
    
    
    
    
