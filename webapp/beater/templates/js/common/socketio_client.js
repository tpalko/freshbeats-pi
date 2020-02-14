socket = io.connect("http://{{socketio_host}}:{{socketio_port}}");

socket.on('connect_response', function(data) {
  console.log(data);
});

socket.on('player_status', function(player_status){

  $("#player_status").html(player_status.current_song);
  
  if (player_status.player.shuffle) {
    $("a[command='toggle_shuffle']").text("shuffle on").removeClass('btn-default').addClass('btn-warning');  
  } else {
    $("a[command='toggle_shuffle']").text("shuffle off").removeClass('btn-warning').addClass('btn-default');  
  }
  
  if (player_status.player.mute) {
    $("a[command='mute']").text("mute on").removeClass('btn-default').addClass('btn-warning');  
  } else {
    $("a[command='mute']").text("mute off").removeClass('btn-warning').addClass('btn-default');  
  }
  
  realignPage();  
});

socket.on('playlist_update', function(playlist){
  $(".playlist").html(playlist);
  $(".playlist")[0].scroll(0, $(".playlist").find(".playlistsong.current")[0].offsetTop - 43);
  
  realignPage();
});

socket.on('alert', function(data){
  console.log(data);
  alert(data.message);
});

socket.on('message', function(data){
  console.log(data);
  showError(data.message);
})
