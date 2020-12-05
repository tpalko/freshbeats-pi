{% load static %}

var socket = io.connect("http://{{socketio_host}}:{{socketio_port}}");

var switchboard_status = 'down';
var switchboard_freshness = undefined;

setInterval(function(){
  now = new Date();
  if (switchboard_freshness == undefined) {
  } else if (now - switchboard_freshness > 7000) {
    if (switchboard_status == 'up') {
      switchboard_status = 'down';
      $("#switchboard_status").removeClass('btn-success').addClass('btn-warning').find("img")[0].src = '{% static "icons/alert-triangle-fill.svg" %}';;
    }
  }
}, 5000);

socket.on('health_response', function(data) {
  console.log(data);
  if (switchboard_status == 'down') {
    // -- any news is good news 
    switchboard_status = 'up';
    $("#switchboard_status").removeClass("btn-warning").addClass("btn-success").find("img")[0].src = '{% static "icons/check-circle.svg" %}';;
  }
  switchboard_freshness = new Date();
});

socket.on('connect_response', function(data) {
  console.log(data);
  $.ajax({
    url: '{% url "register_client" %}',
    data: data,
    dataType: 'json',
    type: 'POST',
    success: function(data, textStatus, jqXHR) {
      console.log(data);
    }, 
    error: function(jqXHR, textStatus, errorThrown) {
      console.log(errorThrown);
    }
  })
});

socket.on('player_status', function(player_status){

  // console.log(player_status);
  
  $("#player_status").html(player_status.current_song);
  
  if (player_status.player.shuffle == "True") {
    $("a[command='toggle_shuffle']").removeClass('btn-default').addClass('btn-warning');  
  } else {
    $("a[command='toggle_shuffle']").removeClass('btn-warning').addClass('btn-default');  
  }
  
  if (player_status.player.mute == "True") {
    $("a[command='toggle_mute']").removeClass('btn-default').addClass('btn-warning');
  } else {
    $("a[command='toggle_mute']").removeClass('btn-warning').addClass('btn-default');
  }
  
  if (player_status.player.state == 'paused') {
    $("a.player-state[command='pause']").removeClass('btn-default').addClass('btn-warning');
    $("a.player-state[command='play']").removeClass('btn-default').addClass('btn-success');
  } else if (player_status.player.state == 'playing') {
    $("a.player-state[command='pause']").removeClass('btn-warning').addClass('btn-default');
    $("a.player-state[command='play']").removeClass('btn-default').addClass('btn-success');
  } else {
    $("a.player-state[command='pause']").removeClass('btn-warning').addClass('btn-default');
    $("a.player-state[command='play']").removeClass('btn-success').addClass('btn-default');
  }
  
  $(".playlist").html(player_status.playlist);
  $("#player_volume").html(player_status.player.volume);
  $("#player_time_pos").html(player_status.player.time_pos_display);
  $("#player_time_remaining").html(player_status.player.time_remaining_display);
  $("#player_percent_pos").html(player_status.player.percent_pos + "%");
  $(".playlist")[0].scroll(0, $(".playlist").find(".playlistsong.current")[0].offsetTop - 43);
  
  realignPage();  
});

socket.on('beatplayer_status', function(beatplayer_status) {
  
  // console.log(beatplayer_status)
  //$("#volume_display").html(player_status.player.beatplayer_volume + "%");
  
  if (beatplayer_status.status == 'ready') {
    $("#beatplayer_status_" + beatplayer_status.id).removeClass("btn-warning").removeClass("btn-danger").addClass("btn-success").find("img")[0].src = '{% static "icons/check-circle.svg" %}';
  } else if (beatplayer_status.status == 'notready') {
    $("#beatplayer_status_" + beatplayer_status.id).removeClass("btn-success").removeClass("btn-danger").addClass("btn-warning").find("img")[0].src = '{% static "icons/alert-triangle-fill.svg" %}';
  } else if (beatplayer_status.status == 'down') {
    $("#beatplayer_status_" + beatplayer_status.id).removeClass("btn-warning").removeClass("btn-success").addClass("btn-danger").find("img")[0].src = '{% static "icons/alert-triangle-fill.svg" %}';
  }
  $("#beatplayer_status_" + beatplayer_status.id).find("img")[0].title = "reachable: " + beatplayer_status.reachable + ", registered: " + beatplayer_status.registered + ", selfreport: " + beatplayer_status.selfreport + ", mounted: " + beatplayer_status.mounted;
  
});

socket.on('append_player_output', function(output) {
  $("#player_output").html($("#player_output").html() + output);
});

socket.on('clear_player_output', function() {
  $("#player_output").html("");
});

socket.on('alert', function(data){
  console.log(data);
  alert(data.message);
});

socket.on('message', function(data){
  console.log(data);
  showError(data);
})
