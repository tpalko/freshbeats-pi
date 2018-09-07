socket = io.connect("http://{{socketio_host}}:{{socketio_port}}");

socket.on('connect_response', function(data) {
  console.log(data);
});

socket.on('player_status', function(data){
  console.log("player_status:");
  console.log(data);
  $("#player_info").html(data);
});

socket.on('player_state', function(data){
  console.log("player_state:");
  console.log(data);
  $("a[command='shuffle']").text("shuffle is " + data.shuffle);
  $("a[command='mute']").text("mute is " + data.mute);
});

socket.on('alert', function(data){
  console.log(data);
  alert(data.message);
});
