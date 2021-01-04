var localVideo;
var localStream;
var remoteVideo;
var peerConnection;
var serverConnection;
var uuid;
var peerid;

var peerConnectionConfig = {
  iceServers: [
    {urls: 'stun:stun.l.google.com:19302'},
    //{urls: 'stun:stun.stunprotocol.org:3478'},
    {urls: "turn:mydevcloud.freedynamicdns.org:3478",username:'user', credential:'test' },
  ]
};

function pageReady() {  
  localVideo = document.getElementById('localVideo');
  remoteVideo = document.getElementById('remoteVideo');

  serverConnection = new WebSocket('wss://' + window.location.hostname + '/gstreamer-browser-webrtc/webrtc-ws');
  serverConnection.onmessage = gotMessageFromServer;
  serverConnection.onclose= on_ws_closed;
  
  console.log("page loaded")
}

function on_ws_closed(){
    console.log("ws-connection closed")
    alert("ws-connection closed. Refresh page")
}

function sendWelcomeMessage(){
    //register at server with uuid   
    var time_str=String(Date.now())
    var str=String(time_str.slice(time_str.length - 5))    
    uuid=document.getElementById('my_uuid').value+"_"+str    
    document.getElementById("show_myuuid").innerHTML=uuid
    
    var constraints = {
        video: document.getElementById("input_video").checked,
        audio: document.getElementById("input_audio").checked
    }; 
    console.log(navigator.mediaDevices) 
    
    if(navigator.mediaDevices.getUserMedia) {
        if(document.getElementById("input_audio").checked ==false && document.getElementById("input_video").checked==false){
            console.log("no local media selected")
            }
        else{
            navigator.mediaDevices.getUserMedia(constraints).then(getUserMediaSuccess).catch(errorHandler);
        }
    } else {
        alert('Your browser does not support getUserMedia API');
    } 
    serverConnection.send(JSON.stringify({"type":"HELLO","uuid":uuid}));
    //setup peerconnection
    peerConnection = new RTCPeerConnection(peerConnectionConfig);
    peerConnection.onicecandidate = gotIceCandidate;
    peerConnection.ontrack = gotRemoteStream;
}

function getUserMediaSuccess(stream) {
  localStream = stream;
  localVideo.srcObject = stream;
}

function init_call(){
    peerid=document.getElementById("peer_list").value
    serverConnection.send(JSON.stringify({"type":"SESSION","peer_id":peerid}));
    }

function start(isCaller) {
    if(localStream != undefined){
        peerConnection.addStream(localStream);
    }
    
    if(isCaller) {
        console.log("create offer")
        peerConnection.createOffer({offerToReceiveAudio: true, offerToReceiveVideo: true}).then(createdDescription).catch(errorHandler);
    }
    else{
        console.log("create answer")
        peerConnection.createAnswer({offerToReceiveAudio: true, offerToReceiveVideo: true}).then(createdDescription).catch(errorHandler);
    }
    document.getElementById("c_register").style.display="none"
    document.getElementById("c_stop").style.display=""
    document.getElementById("c_start").style.display="none"
}

function stop_call(){    
    if(localStream != undefined){    
        var i;
        for (i = 0; i < localStream.getTracks().length; i++) {
            var track = localStream.getTracks()[i];  
            track.stop();
        }
           
        for (i = 0; i < peerConnection.getSenders().length; i++) {
            var sender = peerConnection.getSenders()[i];
            peerConnection.removeTrack(sender)  
        }
    }
    peerConnection.close()
        
    serverConnection.send(JSON.stringify({"type":"EXIT","uuid":uuid}));
    document.getElementById("c_register").style.display=""
    document.getElementById("c_stop").style.display="none"
    document.getElementById("c_start").style.display="none"
    }


function gotMessageFromServer(message) {
  console.log("onmessage")
  console.log(message.data)
  if(message.data=="SESSION_OK"){  
    console.log("session is okay. start call")   
    start(true)
  }
  else if(message.data=="HELLO"){
    document.getElementById("c_register").style.display="none"
    document.getElementById("c_stop").style.display=""
    document.getElementById("c_start").style.display=""
    console.log("Hello recieved. show call button")
  }
  else if(message.data.startsWith("ERROR")){
       console.log(message.data)
       alert(message.data)
  }
  else{
    var signal = JSON.parse(message.data); //fails if no json-format
    if(signal.sdp) {
        if(signal.sdp.type == 'offer') {
            console.log("offer recieved. remote-description set")
            peerConnection.setRemoteDescription(new RTCSessionDescription(signal.sdp)).then(function() {    
                start(false)
            }).catch(errorHandler);
        }
        else if (signal.sdp.type == 'answer'){
            peerConnection.setRemoteDescription(new RTCSessionDescription(signal.sdp)).then(function() {    
                console.log("answer recieved. remote-description set")
            }).catch(errorHandler);
        
        }
    }    
    else if(signal.ice) {
        console.log("ice-candiate recieved")
        peerConnection.addIceCandidate(new RTCIceCandidate(signal.ice)).catch(errorHandler);
    }    
    else if(signal.peers){
        console.log("peers-list update recieved")
        var sel = document.getElementById('peer_list');
        //remove all old ones.. TODO: better compare, add missing and remove inactives
        var length = sel.options.length;
        for (i = length-1; i >= 0; i--) {
            sel.options[i] = null;
        }
        signal.peers.forEach(addpeertoselect)           
    }
    else if(signal.type){
        if(signal.type == "EXIT"){
        //reset page in a fresh state
        stop_call()
        //do not automatically call to re-register
        //sendWelcomeMessage()
        }
    }
  }
}

function gotIceCandidate(event) {
  if(event.candidate != null) {
    serverConnection.send(JSON.stringify({'ice': event.candidate, 'uuid': uuid}));
  }
}

function createdDescription(description) {
  console.log('set local description and send offer/answer');
  peerConnection.setLocalDescription(description).then(function() {
    serverConnection.send(JSON.stringify({'sdp': peerConnection.localDescription}));
  }).catch(errorHandler);
}

function gotRemoteStream(event) {
  console.log('recieved remote stream');
  remoteVideo.srcObject = event.streams[0];
}

function addpeertoselect(value, index, array) {
        if(uuid != value){ //skip own id
            var sel = document.getElementById('peer_list');
            //add all peers
            // create new option element
            var opt = document.createElement('option');
            // create text node to add to option element (opt)
            opt.appendChild( document.createTextNode(value) );
            // set value property of opt
            opt.value = value; 
            // add opt to end of select box (sel)
            sel.appendChild(opt);  
        }   
}

function errorHandler(error) {
  console.log(error);
}
