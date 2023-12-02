require('dotenv').config({ path: './dev.env' })

var cors_origin = process.env.CORS_ORIGIN || ""
var listen_host = process.env.LISTEN_HOST || "127.0.0.1"
var listen_port = process.env.LISTEN_PORT || 8000 
var monitoring_enabled = (process.env.MONITORING_ENABLED || 1) == 1

var cors_origins = cors_origin.split(',')

var restify = require('restify');

// var restifyCors = require('restify-cors');
// var cors = restifyCors({  
//   origins: ['http://127.0.0.1:8100'],
//   allowHeaders: ['authorization']
// })

server = restify.createServer({
  name: "Switchboard",
  url: "0.0.0.0"
}),
socketio = require('socket.io')({
  cors: {
    origin: [cors_origins],
    credentials: true
  }
}),
io = socketio.listen(server.server),
cookie = require('cookie');

http = require('http');
//fs = require('fs');

//Configure socket.io to store cookie set by Django
/*
io.configure(function(){
    io.set('authorization', function(data, accept){
        if(data.headers.cookie){
            data.cookie = cookie.parse(data.headers.cookie);
            console.log('cookie: ' + JSON.stringify(data.cookie));
            return accept(null, true);
        }
        return accept('error', false);
    });
    io.set('log level', 1);
});


io.use(function(socket, next){
  var handshakeData = socket.request;
  //var cookie = socket.handshake.headers.cookie;
  console.log('cookie: ' + JSON.stringify(cookie));
  socket.request['cookie'] = cookie.parse(socket.handshake.headers.cookie);
  next();
});
*/
var sockets = {};

/*
 * Run a small Restify API to enable inbound communications from symbiote web app
 * and serve test client html
 */

// serves up test client html
/*
function rootHandler(req, res) {

  console.log('in rootHandler');
  // -- this doesn't quite work - the readFile occurs asynchronously, so the request has already been served by the time we have the file contents
  fs.readFile('test-client.html', function (err, data) {
    if (err) {
      res.send(500);
      return res.end('Error loading test-client.html');
    }
    res.send(200);
  });

  console.log("already here..");
}
*/

// take inbound generic event requests from django app and pass on to client
function pushEventHandler(req, res, next) {
  
  var connectionId = req.params.connectionId;
  
  console.log("Event: " + req.params.event + " -> " + (connectionId != undefined ? connectionId : "all"));
  // console.log(req.body);
  
  try {

    if(connectionId != undefined) {

      var emitted = false;
      for (remoteAddress in sockets) {
        var socket = sockets[remoteAddress];
        var thisSocketConnectionId = socket.conn.id;
        if (thisSocketConnectionId == connectionId) {
          socket.emit(req.params.event, req.body);  
          emitted = true;
        }
      }
      if (!emitted) {
        console.log("Connection ID " + connectionId + " not registered here");
      }
      
    } else {
      io.sockets.emit(req.params.event, req.body);
    }

    res.send(200, "OK");
  } catch(e){
    console.error(e);
  }
  
  next();
  /*
  var sessionid = req.params.sessionid;

  // send requested socket.io event to appropriate client
  if(sockets[sessionid]) {

    sockets[sessionid].emit(event, req.body);

    res.send(200, "OK");
    next();
  }
  else {
    next(new restify.InvalidArgumentError("Unknown or Invalid client sessionid"));
  }
  */
}

function healthz(req, res, next) {
  res.send(200, 'OK');
  next();
}

function healthPing () {
  console.log("Sending health ping to " + Object.keys(sockets).length + " clients");
  for (remoteAddress in sockets) {
    var socket = sockets[remoteAddress];
    var connectionId = socket.conn.id;
    console.log('Emitting switchboard_health_ping -> ' + connectionId);
    var response = socket.emit('switchboard_health_ping', { health: 'ok' });
    // console.log(response);
    if (!response) {
      console.log("Removing " + connectionId + " from health pings - found disconnected");
      delete socket;
    }
  }
}

//TAG:MONITORING

if (monitoring_enabled) {
  setInterval(healthPing, 5000);
} else {
  console.log("Monitoring has been disabled (MONITORING_ENABLED=" + monitoring_enabled + ")")
}

// server.use(
//   function crossOrigin(req, res, next) {
//     console.log("Adding ACAO/ACAH")
//     res.header("Access-Control-Allow-Origin", "*");
//     res.header("Access-Control-Allow-Headers", "X-Requested-With");
//     return next();
//   }
// )

server.use(restify.plugins.queryParser());
server.use(restify.plugins.bodyParser());

server.use((incomingMessage, serverResponse, next) => {
  // console.log(incomingMessage);
  // console.log(serverResponse);
  // console.log(next);
  
  next();
})

//server.get('/', rootHandler);
server.post('/pushevent/:event', pushEventHandler);
server.post('/pushevent/:event/:connectionId', pushEventHandler);
server.get('/healthz', healthz)

server.listen(listen_port, listen_host, function(){
  console.log('%s listening at %s', server.name, server.url);
});

/*
 * Socket.io top-level event definition. Defined what actions the serve takes
 * when a client connects, and sets up all events to listen for from
 * the client.
 */

io.sockets.on('connection', function (socket) {

  console.log(socket.handshake.time + ': Connection attempt - ' + socket.client.conn.remoteAddress);
  console.log(socket.handshake.time + ': ' + socket.handshake.headers['user-agent']);
  
  /*
  cookie_data = socket.handshake.headers.cookie;//['sessionid'];
  parsed_cookie = cookie.parse(cookie_data);
  sockets[parsed_cookie.io] = socket;
  */
  
  sockets[socket.client.conn.remoteAddress] = socket;

  var sessionInfo = { 
    message: 'Socket.IO connection made', 
    connectionId: socket.conn.id, 
    userAgent: socket.handshake.headers['user-agent'], 
    remoteAddress: socket.client.conn.remoteAddress 
  };
  
  console.log(sessionInfo);
  socket.emit('connect_response', sessionInfo);
});
