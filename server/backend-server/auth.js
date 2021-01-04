
let jwt = require('jsonwebtoken');
const fs = require('fs');

//TO DO make arguments of class + add remaining functions to class
const JWT_TAG="JWT_WS"
const JWT_SECRET=process.env.JWT_SECRET || 'usertest';
const PATH_LOGIN='./client/login.html'
const APP_NAME=process.env.APP_NAME || '/gstreamer-browser-webrtc';
const PATH_SUCCESS=APP_NAME+'/access/index.html'
const PATH_ACCESS='./client'

function createAuthToken(id, agent, guidUser) {
    var sign = JWT_SECRET;
    var package = { 'device': id, 'access': 'authenticated', 'agent': agent, 'user': guidUser }
    return jwt.sign(package, sign, { expiresIn: '30 days' });
};

var get_cookies = function(request) {
  var cookies = {};
  request.headers && request.headers.cookie.split(';').forEach(function(cookie) {
    var parts = cookie.match(/(.*?)=(.*)$/)
    cookies[ parts[1].trim() ] = (parts[2] || '').trim();
  });
  return cookies;
};

class HandlerGenerator {
  notregistered (req, res) { 
        res.writeHead(200, {'Content-Type': 'text/html'});    
        return res.end(fs.readFileSync(PATH_LOGIN));
  }
  login (req, res) {    
    let username = req.body.username;
    let password = req.body.password;
    // For the given username fetch user from DB
    //simply get the pwd from the config-file
    let mockedUsername = process.env.HTTP_USER || 'user';
    let mockedPassword = process.env.HTTP_PWD || 'test';

    if (username && password) {
      if (username === mockedUsername && password === mockedPassword) {
        var body = req.body;
        var updatedToken = createAuthToken(body.device, body.userAgent, body.user);
        var newDate = new Date();
        var expDate = newDate.setMonth(newDate.getMonth() + 1)
        if(req.secure){
            res.cookie(JWT_TAG, updatedToken, {secure:true, maxAge: expDate });
        }
        else{
            res.cookie(JWT_TAG, updatedToken, {secure:false, maxAge: expDate });
            }
        res.send(PATH_SUCCESS)
        } 
      else {        
        //res.write('Authentication failed! Please check the request');
        res.status(403);        
        res.end();       
        }     
    }
    else{
        res.status(403);        
        res.end();    
    }
  }
  access (req, res) {
    res.sendFile('.'+req.url,{ root: PATH_ACCESS });
  }
  checkToken (req, res, next) {
      if(req.headers.cookie != undefined){
        var token = req.headers.cookie.split(JWT_TAG+"=")[1]
      }
      else{
          token=false
      }
      if (token) {
        if (token.startsWith('Bearer ')) {
        // Remove Bearer from string
        token = token.slice(7, token.length);
        }
        jwt.verify(token, JWT_SECRET, (err, decoded) => {
          if (err) {
            res.writeHead(403, {'Content-Type': 'text/html'});    
            return res.end(fs.readFileSync(PATH_LOGIN));
          } else {
            req.decoded = decoded;
            next();
          }
        });
      } else {
        res.writeHead(403, {'Content-Type': 'text/html'});    
        return res.end(fs.readFileSync(PATH_LOGIN));
        }
    }
    check_token_return(req){
        var token=get_cookies(req)[JWT_TAG]
        if (token== undefined){return false}
        if (token.startsWith('Bearer ')) {
            // Remove Bearer from string
            token = token.slice(7, token.length);
        }
        jwt.verify(token, JWT_SECRET, (err, decoded) => {
            if (err) {return false;} 
            else {return true;}
        });
    }
}

module.exports ={
    HandlerGenerator,
}


