var restify = require('restify'),
server = restify.createServer({
  name: "Switchboard"
}),
socketio = require('socket.io')({
  // -- options
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

  //console.log(req.params.event);
  //console.log(req.body);
  io.sockets.emit(req.params.event, req.body);

  res.send(200, "OK");
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

server.use(restify.plugins.queryParser());
server.use(restify.plugins.bodyParser());

//server.get('/', rootHandler);
server.post('/pushevent/:event', pushEventHandler);

server.listen(3333, function(){
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

  socket.emit('connect_response', { message: 'Socket.IO connection made' });
});
