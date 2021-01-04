const HTTPS_PORT = 8443;
const express = require('express');
const bodyParser = require('body-parser');
const fs = require('fs');
const https = require('https');
const WebSocket = require('ws');
const WebSocketServer = WebSocket.Server;

const auth = require('./auth.js')

var peers = {};
var session={};
const DOMAIN=process.env.HOST_DNS || 'mydevcloud.freedynamicdns.org';

// Yes, TLS is required
const serverConfig = {
  key: fs.readFileSync('/etc/letsencrypt/live/'+DOMAIN+'/privkey.pem'),
  cert: fs.readFileSync('/etc/letsencrypt/live/'+DOMAIN+'/cert.pem'),
};

let app = express(); // Export app for other routes to use
let handlers = new auth.HandlerGenerator();
app.use(bodyParser.urlencoded({ extended: true}));
app.use(bodyParser.json());  
// Routes & Handlers
app.post('/logindata', handlers.login);
app.get('/',handlers.notregistered);
app.use('/access',handlers.checkToken,handlers.access);//host "public" files

const httpsServer = https.createServer(serverConfig, app);
httpsServer.listen(HTTPS_PORT, '0.0.0.0');

httpsServer.on('upgrade', function upgrade(request, socket, head) {
  //This function is not defined on purpose. Implement it with your own logic.
   console.log("on upgrade",request.headers.cookie)    
   validated=handlers.check_token_return(request)
   
    if(validated==false) {
          socket.write('HTTP/1.1 401 Unauthorized\r\n\r\n');
          socket.destroy();
          return;
    }            
    wss.handleUpgrade(request, socket, head, function done(ws) {
          wss.emit('connection', ws, request);
        });
});

// Create a server for handling websocket calls
const wss = new WebSocketServer({ noServer: true });

wss.on('connection', function(ws,req) {
      ws.on('message', function(message) {
        // Handle incoming message
        console.log('received: %s', message);
        var json_obj=JSON.parse(message);
        if(json_obj['type']=='HELLO'){               
            peers[json_obj['uuid']]=ws        
            //send message to sender
            wsclient=peers[json_obj['uuid']]
            wsclient.send("HELLO")
            console.log(Object.keys(peers))
            // send message to all with registered peers
            notify_all_peers()
        }
        else if(json_obj['type']=="SESSION"){
            //Send message to peer_id ws_client
            if (json_obj['peer_id'] in peers){            
                if(json_obj['peer_id'] in session){
                    ws.send("ERROR Peerid is already in a session") //feedback to sender
                }
                else{
                    sender_peer=getKeyByValue(peers,ws)           
                    sender_peer=sender_peer
                    session[json_obj['peer_id']]=sender_peer
                    session[sender_peer]=json_obj['peer_id']                                
                    ws.send("SESSION_OK") 
                    console.log("SESSION_OK")
                }
            }
            else{
                ws.send("ERROR Peerid not registered") //feedback to sender
            }
        }
        else if(json_obj['type']=="EXIT"){
            //inform partner_peer if any
            sender_peer=getKeyByValue(peers,ws)
            if (sender_peer in session){
                    partner_peer=session[sender_peer] 
                    if (partner_peer in peers){
                        ws_partner=peers[partner_peer]
                        if (ws_partner.readyState == WebSocket.OPEN){                        
                            ws_partner.send(message) 
                    }
                }
            }         
            //remove peer
            sender_peer=getKeyByValue(peers,ws)        
            remove_peer(sender_peer)
        }
        else{
            
            sender_peer=getKeyByValue(peers,ws)        
            if (sender_peer==undefined){
                console.log("ERROR no peer in session found")
                ws.send("ERROR no peer in session found")
            }
            else{
                partner_peer=session[sender_peer]  
                console.log("from: ",sender_peer," to:",partner_peer)                    
                wsclient=peers[partner_peer]                        
                wsclient.send(message) 
            }
        }
      });
});
// Hearbeart - Start ---------------------------
wss.on('close', function close() {
    
  clearInterval(interval);
});
// Hearbeart - End ---------------------------

// Helper - functions - Start -----------------------------------------------------------------------------------
function getKeyByValue(object, value) {
  //Returns the key for given value in an object
  return Object.keys(object).find(key => object[key] === value);
}

function notify_all_peers(){
    //Notifies all peers about current registered peers 
    //remove peers if their readyState =! WebSocket.OPEN
    let uuid_array=Object.keys(peers)
    var i;
    for (i = 0; i < uuid_array.length; i++) {
        wsclient=peers[uuid_array[i]]    
        if (wsclient.readyState == WebSocket.OPEN){    
            wsclient.send(JSON.stringify({"peers":uuid_array}))
        }
        else{
            //remove peer
            remove_peer(uuid_array[i])
        }
    }
}

function remove_peer(peerid){
    //remove peer for peers and session-dict
    if(peerid in session){
        //remove peer also if in an active session
        partner_peer=session[peerid]
        delete session[partner_peer]
        delete session[peerid]
    }
    //peers[peerid].terminate() //=ws.terminate()
    delete peers[peerid]    
    console.log(Object.keys(peers))
}
// Helper - functions - End -----------------------------------------------------------------------------------

// Hearbeart - Start ---------------------------

const interval = setInterval(function ping() {
    // Continously calls every x ms, 
    // check for disconnected clients, informs partner-peers and removes them from list
    var new_peers=false
    Object.keys(peers).forEach(function each(id) {
        ws=peers[id]
        if(ws.readyState != WebSocket.OPEN){
            new_peers=true
            //notify partner-peer to EXIT
            if(id in session){
                partner_peer=session[id]            
                ws_partner=peers[partner_peer]
                if (ws_partner.readyState == WebSocket.OPEN){
                    ws_partner.send(JSON.stringify({"type":"EXIT","uuid":id})) 
                }
            }
            //remove peer            
            remove_peer(id)        
        }
    });
    if(new_peers){
        //notify others of remaining peers
        notify_all_peers()
    }
}, 3000);
// Hearbeart - End ---------------------------

console.log('Server running. Visit https://localhost:' + HTTPS_PORT + ' in Firefox/Chrome.\n\n\
  * Note the HTTPS; there is no HTTP -> HTTPS redirect.\n\
  * You will need to accept the invalid TLS certificate.\n\
  * To access the server from outside, check your firewall settings for port '+ HTTPS_PORT+' .'
);
