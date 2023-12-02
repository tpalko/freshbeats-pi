const { Server } = require("socket.io");
const io = new Server({});

var sockets = {};

function healthz(req, res, next) {
  res.send(200, 'OK');
  next();
}

setInterval(function() {
  // console.log("Sending health ping to " + Object.keys(sockets).length + " clients");
  for (connectionId in sockets) {
    console.log('Emitting switchboard_health_ping -> ' + connectionId);
    var response = sockets[connectionId].emit('switchboard_health_ping', { health: 'ok' });
    if (!response.connected) {
      console.log("Removing " + connectionId + " from health pings - found disconnected");
      delete sockets[connectionId];
    }
  }
}, 5000);

io.sockets.on('connection', function (socket) {

  console.log(socket.handshake.time + ': Connection attempt - ' + socket.client.conn.remoteAddress);
  console.log(socket.handshake.time + ': ' + socket.handshake.headers['user-agent']);
  
  /*
  cookie_data = socket.handshake.headers.cookie;//['sessionid'];
  parsed_cookie = cookie.parse(cookie_data);
  sockets[parsed_cookie.io] = socket;
  */
  
  sockets[socket.conn.id] = socket;

  var sessionInfo = { 
    message: 'Socket.IO connection made', 
    connectionId: socket.conn.id, 
    userAgent: socket.handshake.headers['user-agent'], 
    remoteAddress: socket.client.conn.remoteAddress 
  };
  
  console.log(sessionInfo);
  socket.emit('connect_response', sessionInfo);
});

console.log("Listening on port 3000..");
io.listen(3000);
