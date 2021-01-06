#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jan  6 10:42:14 2021

@author: klaus
"""
import sys, os
sys.path.append(os.path.join(sys.path[0],'h264-profile-level-id'))
import h264_profile_level_id.core as h264profilereader

def convert_intlevel_to_string(level):
    if(level==0):
        level_string="1b"
    elif(level==1):
        level_string="1"
    elif(level % 10 ==0):
        level_string=str(level)[0]
    else:
        level_string=str(level)[0]+"."+str(level)[1]
    return level_string

def convert_level_str_to_int(level):
    if(level=="1b"):
        return 0
    elif(len(level)==1):
        return  int(level)*10       
    elif("." in level):
        return int(level[0])*10+int(level[2])    

PROFILES = {
        1: "constrained-baseline",
        2: "baseline",
        3: "main",
        4: "constrained-high",
        5: "high",    
    }

def convert_intprofile_to_string(profile):    
    return PROFILES.get(profile)

def convert_profile_string_to_int(profile):
    for key,value in PROFILES.items():
        if profile==value:
            return key
  
def get_caps_from_profileid(profileid):
    profile=h264profilereader.parseProfileLevelId(profileid)
    level_str=convert_intlevel_to_string(profile.level)
    profile_str=convert_intprofile_to_string(profile.profile)
    caps_str="video/x-h264,profile=(string){},level=(string){}".format(profile_str,level_str)
    return caps_str

def get_omxcaps_from_caps(caps_str):
    temp=caps_str.split('profile-level-id=(string)')[1]
    profile_id=temp.split(",",1)[0]
    return get_caps_from_profileid(profile_id)  
    