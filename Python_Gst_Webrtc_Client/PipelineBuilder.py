#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Dec 22 11:38:18 2020

@author: klaus
"""
import profileconverter_h264 as utilh264
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst,GLib
import time

import logging as logger
logger.basicConfig(format='%(asctime)s %(message)s',level=logger.INFO)

MEDIA_PRIO={
        "video":{"H264":3,"VP8":2,"VP9":1},
        "audio":{"OPUS":1}
        }

MEDIA={
        "H264":{"encoder":"omxh264enc","payloader":"rtph264pay","pt":100},
        "VP8":{"encoder":"vp8enc","payloader":"rtpvp8pay","pt":96},
        "VP9":{"encoder":"vp9enc","payloader":"rtpvp9pay","pt":98},
        "OPUS":{"encoder":"opusenc","payloader":"rtpopuspay","pt":111},
        }

class SDPTester():
    def __init__(self):    
        self.media=MEDIA
        self.media_prio=MEDIA_PRIO
        self.webrtcmedia=dict()
        self.pipe=None        
    
    def set_encoder_to_livestream(self,enc_element,encoder_name):
        if(encoder_name=="x264enc"):#this speeds up the tests significantly            
            enc_element.set_property("tune","zerolatency")
        elif(encoder_name=="vp8enc" or encoder_name=="vp9enc"):            
            enc_element.set_property("deadline",75000)#750ms~2Frames at 30FPS   
            
    def create_testpipeline(self,media_type,encoder,payloader,test_caps):
        if(media_type=="video"):
            source='videotestsrc is-live=true ! video/x-raw,width=120,height=80 ! videoconvert '
        elif(media_type=="audio"):
            source='audiotestsrc is-live=true wave=blue-noise ! audioconvert ! audioresample '             
        description_pipeline='''{source} ! {encoder} name=encoder ! {payloader} ! capsfilter caps="{caps}" ! fakesink name=fakesinktest '''.format(source=source,encoder=encoder,payloader=payloader,caps=test_caps.to_string())
        if(encoder=="omxh264enc"):
            #TOFIX with videotestsrc a sigsev is caused if capsomx="video/x-h264,level=(string)XX" is defined
            #is level required to be set for encoder or enough to set before fakesink?
            source="v4l2src device=/dev/video0 ! video/x-raw,width=120,height=80,framerate=30/1  ! videoconvert"
            caps_omx=utilh264. get_omxcaps_from_caps(test_caps.to_string())
            description_pipeline='''{source} ! {encoder} name=encoder ! capsfilter caps="{capsomx}" ! {payloader} ! capsfilter caps="{caps}" ! fakesink name=fakesinktest '''.format(source=source,encoder=encoder,payloader=payloader,capsomx=caps_omx,caps=test_caps.to_string())
        print(description_pipeline)
        self.pipe = Gst.parse_launch(description_pipeline)
        self.set_encoder_to_livestream(self.pipe.get_by_name('encoder'),encoder)

    def test_pipeline(self,media_type,encoder_name,test_caps,store_caps):
        encoder=self.media[encoder_name]['encoder']
        payloader=self.media[encoder_name]['payloader']                   
        logger.info("Test-started for {} with encoder {} and caps {}".format(media_type,encoder_name,test_caps))
        if(self.media[encoder_name]['encoder']=="omxh264enc"):
            store_caps="output"
            
        self.create_testpipeline(media_type,encoder,payloader,test_caps)       
    
        self.start_pipeline()
        while(Gst.StateChangeReturn.ASYNC ==self.pipe.get_state(0)[0]):
            time.sleep(0.002)
            
        if(self.pipe.get_state(0)[0]==Gst.StateChangeReturn.SUCCESS):
            self.success=True
            caps=self.pipe.get_child_by_name("fakesinktest").sinkpads[0].get_current_caps()
            logger.info("caps of fakesink: {} \n".format(caps.to_string()))
            self.media[encoder_name]['negotiated']=True
            
            if(store_caps=="output"):                
                #create new caps with a reduced set of fields
                cap_struc=caps.get_structure(0)  
                for field in ['sprop-parameter-sets','timestamp-offset','seqnum-offset']:#'sprop-parameter-sets'
                    if(cap_struc.has_field(field)):                        
                        cap_struc.remove_field(field)                
                reduced_caps=Gst.Caps.new_empty()
                reduced_caps.append_structure(cap_struc)                               
                self.media[encoder_name]["caps"]=reduced_caps
            elif(store_caps=="input"):  
                self.media[encoder_name]["caps"]=test_caps.copy()
                
            elif(store_caps=="none"):
                pass            
        else:            
            self.success=False                                        
                
        self.stop_pipeline() 
        logger.info("Pipeline-Test-result: {} \n".format(self.success))
        return self.success
        
    def check_caps(self,media,validate_caps,store_caps):
        for k in range(media.formats_len()):                                                        
            caps=media.get_caps_from_media(int(media.get_format(k)))  
            for m in range (caps.get_size()):#most likly caps.get_size()=1        
                cap_struc=caps.get_structure(m)  
                encoding_name=cap_struc.get_value("encoding-name")                              
                cap_struc.set_name('application/x-rtp')
                #new caps is required to be able to change the name of the struc from application/x-unknown
                test_caps=Gst.Caps.new_empty()
                test_caps.append_structure(cap_struc)               
                if(encoding_name in self.media and self.media[encoding_name].get('negotiated',False)==False):   
                    if(validate_caps==True):
                        if not(self.test_pipeline(media.get_media(),encoding_name,test_caps,store_caps=store_caps)):                                    
                            logger.info("spd-line is not compatibel with gstreamer pipeline")   
                    else:
                        self.media[encoding_name]['negotiated']=True
                else:
                    logger.info("not supported encoding or already negotiated")
        #check for highest supportted codec:
        for key, value in sorted(self.media_prio[media.get_media()].items(), key=lambda item: item[1],reverse=True):
            if(self.media.get(key,{}).get('negotiated',False)==True):
                self.webrtcmedia[media.get_media()]=key  
                return True  
        
        logger.warning("Warning no supported codec for sending: {}".format(media.get_media()))
        return False                
     
    def analyse_incoming_sdp(self,sdpmsg,media_type,validate_caps,store_caps):
        logger.info("analyse incoming sdp") 
        for j in range(sdpmsg.medias_len()):#loop over offered media-streams/types
            media=sdpmsg.get_media(j)            
            if(media.get_media() == media_type):
                self.check_caps(media,validate_caps,store_caps)
            else:
                logger.info("media-type of sdp {} not supported".format(media.get_media()))
                
    def start_pipeline(self):
        self.pipe.set_state(Gst.State.PLAYING)
                
    def stop_pipeline(self):
        self.pipe.set_state(Gst.State.NULL)  
    
class PipelineBuilder():
    def __init__(self,description_pipeline):        
        self.pipe = Gst.Pipeline()
        self.webrtc = Gst.ElementFactory.make("webrtcbin","webrtc")
        self.pipe.add(self.webrtc)

        self.webrtc=self.pipe.get_by_name('webrtc')
        self.sdptester=SDPTester()
        
    def start_pipeline(self):
        self.pipe.set_state(Gst.State.PLAYING)
        
    def stop_pipeline(self):
        self.pipe.set_state(Gst.State.NULL) 
        self.sdptester=SDPTester()
    
    def get_media(self):
        return self.sdptester.media
    
    def get_mediaprio(self):
        return self.sdptester.media_prio
    
    def get_webrtcmedia(self):
        return self.sdptester.webrtcmedia
    
    def generate_caps(self,media_type,encoder,caps0):
        caps_str='''application/x-rtp, payload=(int){}'''.format(self.get_media()[encoder]['pt'])       
        capsn= Gst.caps_from_string(caps_str)
        if(self.sdptester.test_pipeline(media_type,encoder,capsn,store_caps="output")):                        
            capsn=self.get_media()[encoder]["caps"]
            if caps0==None:
                caps0 = capsn.copy()
            else:
                caps0.append(capsn)
        return caps0
    def check_sdp(self,sdpmsg,media_type,validate_caps,store_caps):
        self.sdptester.analyse_incoming_sdp(sdpmsg,media_type,validate_caps,store_caps)
        
    def add_decodebin(self,pad):
        if pad.direction != Gst.PadDirection.SRC:
            logger.info("pad {} has not src-direction. Pad probably for outgoing-stream. Ignore".format(pad.name))
            return        
        decodebin = Gst.ElementFactory.make('decodebin')
        decodebin.connect('pad-added', self.build_incoming_pipeline)
        self.pipe.add(decodebin)
        decodebin.sync_state_with_parent()
        self.webrtc.link(decodebin)
        
    def build_incoming_pipeline(self,_,pad):
        if not pad.has_current_caps():
            logger.warning('{} has no caps, ignoring'.format(pad))
            return
        caps = pad.get_current_caps()
        name = caps.to_string()
        if name.startswith('video'):
            logger.info("build incoming pipeline for video")
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
            logger.info("build incoming pipeline for audio")
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
        
    def dispose_src(src):
        src.set_state(Gst.State.NULL)
        
    def remove_elements(self,d_elements):
         for element in d_elements:                  
            self.pipe.remove(element)                        
            element.unparent()
            GLib.idle_add(self.dispose_src, element)
            element=None
    
    def remove_raw_pipeline(self,media_type,last_pad):    
        element=last_pad.parent
        delete_elements=[element]
        while(element.numsinkpads!=0):
            previous_element=element.sinkpads[0].get_peer().parent
            delete_elements.append(previous_element)
            element=previous_element
        self.remove_elements(delete_elements)
        logger.info("Unlinked and removed elements from src to {}".format(last_pad.parent.name))
        
        
    def remove_encoder_pipeline(self,media_type):
        #unlink element before webrtc
        queue=self.pipe.get_by_name(media_type+"queue")
        webrtc_pad=queue.srcpads[0].get_peer()
        queue.unlink(self.webrtc)
        #queue.release_request_pad(webrtc_pad)#test
        delete_elements=list()
        delete_elements.append(queue)   
        #unlink encoder 
        encoder=self.pipe.get_by_name(media_type+"enc")
        last_element=encoder.sinkpads[0].get_peer().parent
        last_element.unlink(encoder)
        element=encoder
        
        while(element.srcpads[0].is_linked()):      
            #get all elements between encoder an unlinked queue-element
            next_element=element.srcpads[0].get_peer().parent            
            element.unlink(next_element)
            delete_elements.append(element)
            element=next_element
        self.remove_elements(delete_elements)
        logger.info("Unlinked and removed elements from {} to {}".format(last_element.name,webrtc_pad.parent.name))
        return last_element.sinkpads[0],webrtc_pad    
        
    def build_raw_pipeline(self,media_type):       
        srcelement=Gst.ElementFactory.make(media_type+"testsrc") 
        srcelement.set_property("is-live","true")
        mediaconvert=Gst.ElementFactory.make(media_type+"convert")        
        queue=Gst.ElementFactory.make("queue",media_type+"base")
        
        self.pipe.add(srcelement)
        self.pipe.add(mediaconvert)
        self.pipe.add(queue)
        if(media_type=="video"):
            caps = Gst.Caps.from_string("video/x-raw,width={width},height={height}".format(width=120,height=80))     
            capsfilter = Gst.ElementFactory.make("capsfilter")
            capsfilter.set_property("caps", caps)            
            clockoverlay=Gst.ElementFactory.make("clockoverlay")
            self.pipe.add(capsfilter)
            self.pipe.add(clockoverlay)
            
            srcelement.link(capsfilter)
            capsfilter.link(clockoverlay)
            clockoverlay.link(mediaconvert)
            mediaconvert.link(queue)
            
        if(media_type=="audio"):
            srcelement.set_property("wave","blue-noise")
            srcelement.set_property("volume",0.1)
            audioresample=Gst.ElementFactory.make("audioresample")
            self.pipe.add(audioresample)
            
            srcelement.link(mediaconvert)
            mediaconvert.link(audioresample)
            audioresample.link(queue)
            
        self.pipe.sync_state_with_parent()
        return queue.srcpads[0]               
            
    def build_encoder_pipeline(self,start_pad,end_pad,media_type):
        encoder_name=self.sdptester.webrtcmedia[media_type]
        
        enc = Gst.ElementFactory.make(self.sdptester.media[encoder_name]['encoder'],media_type+"enc")
        
        self.sdptester.set_encoder_to_livestream(enc,self.sdptester.media[encoder_name]['encoder'])
                  
        payloader=Gst.ElementFactory.make(self.sdptester.media[encoder_name]['payloader'],media_type+"pay")
        #payloader.set_property("pt",self.sdptester.media[encoder_name]['pt'])
        
        queue=Gst.ElementFactory.make("queue",media_type+"queue")  
        print(self.sdptester.media[encoder_name]['encoder'])
        print(self.sdptester.media[encoder_name]['caps'])        
        capsfilter = Gst.ElementFactory.make("capsfilter", media_type+"filter")
        caps=self.sdptester.media[encoder_name]['caps']        
        capsfilter.set_property("caps", caps)
        if(self.sdptester.media[encoder_name]['encoder']=='omxh264enc'):
            capsfilter0 = Gst.ElementFactory.make("capsfilter", media_type+"filteromx")
            caps_omx=utilh264. get_omxcaps_from_caps(caps.to_string())
            caps0=Gst.Caps.from_string(caps_omx)
            capsfilter0.set_property("caps", caps0) 
            self.pipe.add(capsfilter0)        
        
        self.pipe.add(enc)
        self.pipe.add(payloader)
        self.pipe.add(capsfilter)
        self.pipe.add(queue)
        self.pipe.sync_children_states()
        start_pad.parent.link(enc)
        
        if(self.sdptester.media[encoder_name]['encoder']=='omxh264enc'):
            enc.link(capsfilter0)
            capsfilter0.link(payloader)            
        else:       
            enc.link(payloader)
            
        payloader.link(capsfilter)
        capsfilter.link(queue)
        if(end_pad==None):
            queue.link(self.webrtc)
        else:    
            queue.link(end_pad.parent)
        
        self.pipe.sync_state_with_parent()                
        
    def build_outgoing_pipeline(self,pad,probeinfo,media_type): 
        logger.info("build_outgoing_pipeline for {}".format(media_type))
        start_pad,end_pad=self.remove_encoder_pipeline(media_type)
        self.remove_raw_pipeline(media_type,start_pad)
        first_open_pad=self.build_raw_pipeline(media_type)        
        self.build_encoder_pipeline(first_open_pad,end_pad,media_type)
        #Removes the probe secure if probe has not be regisered yet, as it was called directly
        return Gst.PadProbeReturn.REMOVE
    
    def build_outgoing_pipeline2(self,media_type): 
        logger.info("build_outgoing_pipeline for {}".format(media_type))
        first_open_pad=self.build_raw_pipeline(media_type)        
        self.build_encoder_pipeline(first_open_pad,None,media_type)
