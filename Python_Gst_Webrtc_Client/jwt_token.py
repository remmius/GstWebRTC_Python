#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Aug 24 09:57:52 2020

@author: klaus
"""
import requests
HTTP_USER='user'
HTTP_PWD='test'
DEFAULT_DOMAIN= 'mydevcloud.freedynamicdns.org'
DEFAULT_APPNAME='/gstreamer-browser-webrtc'

def get_token(user=HTTP_USER,pwd=HTTP_PWD,url="https://"+DEFAULT_DOMAIN+DEFAULT_APPNAME+"/logindata",JWT_TAG="JWT_WS"):
    r= requests.post(url,data={"username":HTTP_USER,"password":HTTP_PWD})#,verify=USE_SSL)
    if(r.status_code==200):
        print("Got the token from the backend")
        return r.cookies.get(JWT_TAG)
    else:
        print("ERROR. Could not get jw-token. \n",r.status_code)        
        return None

if __name__=='__main__':                
 token=get_token()
