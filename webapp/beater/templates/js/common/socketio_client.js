{% load static %}

var socket = io.connect("http://{{socketio_host}}:{{socketio_port}}");

var switchboard_status = 'down';
var switchboard_freshness = undefined;

function set_switchboard_up() {
  switchboard_status = 'up';
  $("#switchboard_status").removeClass("btn-warning").addClass("btn-success").find("img")[0].src = '{% static "icons/check-circle.svg" %}';;
}

function set_switchboard_down() {
  switchboard_status = 'down';
  $("#switchboard_status").removeClass('btn-success').addClass('btn-warning').find("img")[0].src = '{% static "icons/exclamation-triangle-fill.svg" %}';;
}

// if switchboard stops talking to us as a registered client 
// the light goes out eventually 
setInterval(function(){
  now = new Date();
  if (switchboard_freshness == undefined) {
    // -- do nothing 
  } else {

    not_fresh = now - switchboard_freshness > 7000

    if (not_fresh && switchboard_status == 'up') {
      set_switchboard_down();
    }
  }
}, 5000);

socket.on('change_device', function(data) {
  console.log('change device response: ' + JSON.stringify(data) + '. setting selected device');
  $("#device_select").val(data.device_id);
  $("#device_select").trigger("change");
})

//  on startup, switchboard hits this for all registered connection IDs via setInterval
socket.on('switchboard_health_ping', function(data) {
  console.log('switchboard health ping: ' + JSON.stringify(data));

  switchboard_freshness = new Date();

  if (switchboard_status == 'down') {
    // -- any news is good news 
    set_switchboard_up();
  }  

  return true;
});

// on connect, switchboard hits us back here 
// and we go straight back to the server to populate the session 
socket.on('connect_response', function(data) {
  console.log('switchboard connect response: ' + JSON.stringify(data) + " -- now calling register_client");
  $.ajax({
    url: '{% url "register_client" %}',
    data: data,
    dataType: 'json',
    type: 'POST',
    success: function(data, textStatus, jqXHR) {      
      console.log('register client: ' + JSON.stringify(data));
    }, 
    error: function(jqXHR, textStatus, errorThrown) {
      console.error('register client error: ' + textStatus);
      console.error(errorThrown);
    }
  })
});

socket.on('player_status', function(player_status){

  console.log('player status (length ' + JSON.stringify(player_status).length + ')');
  
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
  
  $("#playlist").html(player_status.playlist);
  $("#player_volume").html(player_status.player.volume);
  $("#player_time_pos").html(player_status.player.time_pos_display);
  $("#player_time_remaining").html(player_status.player.time_remaining_display);
  $("#player_percent_pos").html(player_status.player.percent_pos + "%");

  var current_playlistsong = $("#playlist_songs").find(".playlistsong.current")[0];
  if (current_playlistsong != undefined) {
    if (playlist_scrolled_at === undefined || now - playlist_scrolled_at > 5000) {
      $("#playlist_songs")[0].scroll(0, current_playlistsong.offsetTop - 43);
    }
  }
  
  realignPage();  
});

function removeIfPresent(fromElement, classNames) {
  if (Array.isArray(classNames)) {
    console.log(classNames + ' is not an array, fixing that')
    classNames = Array.from(classNames);
  }
  for(var i=0; i<classNames.length; i++) {
    var className = classNames[i];
    console.log('checking for class ' + className);
    if(fromElement.hasClass(className)){
      console.log('sure found ' + className);
      fromElement.removeClass(className);
    }  
  }
}

function addIfNotPresent(toElement, className) {
  if(!toElement.hasClass(className)) {
    toElement.addClass(className);
  }
  return toElement;
}

all_classes = ['btn-success', 'btn-warning', 'btn-danger'];
beatplayer_status_classes = {
  'ready': 'btn-success',
  'notready': 'btn-warning',
  'down': 'btn-danger'
}
beatplayer_status_icons = {
  'ready': 'icons/check-circle.svg',
  'notready': 'icons/exclamation-triangle-fill.svg',
  'down': 'icons/exclamation-triangle-fill.svg'
}
 
// beatplayer_status is hit at the bottom of device context, found here:
//  - healthz 
//  - reassign_device
//  - run_health_loop
//  - check_if_health_loop
socket.on('beatplayer_status', function(beatplayer_status) {
  
  // console.log(beatplayer_status);
  // console.log('beatplayer status: ' + JSON.stringify(beatplayer_status));
  //$("#volume_display").html(player_status.player.beatplayer_volume + "%");
  
  
  const ele = $("#beatplayer_status_" + beatplayer_status.id);
  all_classes.forEach((c) => { ele.removeClass(c); })
  ele.addClass(beatplayer_status_classes[beatplayer_status.status]);
  const staticPath = '{% static "000" %}';
  const iconPath = staticPath.replace(/000/, beatplayer_status_icons[beatplayer_status.status]);
  
  if (!ele.find("img")[0].src.endsWith(iconPath)) {
    ele.find("img")[0].src = iconPath;
  }
  
  // if (beatplayer_status.status == 'ready') {
  //   removeIfPresent(ele, ['btn-warning', 'btn-danger']);
  //   addIfNotPresent(ele, "btn-success");
  //   if (!ele.find("img")[0].src.endsWith('{% static "icons/check-circle.svg" %}')) {
  //     ele.find("img")[0].src = '{% static "icons/check-circle.svg" %}';
  //   }
  // 
  //   // $("#beatplayer_status_" + beatplayer_status.id).removeClass("btn-warning").removeClass("btn-danger").addClass("btn-success").find("img")[0].src = '{% static "icons/check-circle.svg" %}';
  // } else if (beatplayer_status.status == 'notready') {
  //   $("#beatplayer_status_" + beatplayer_status.id).removeClass("btn-success").removeClass("btn-danger").addClass("btn-warning").find("img")[0].src = '{% static "icons/exclamation-triangle-fill.svg" %}';
  // } else if (beatplayer_status.status == 'down') {
  //   $("#beatplayer_status_" + beatplayer_status.id).removeClass("btn-warning").removeClass("btn-success").addClass("btn-danger").find("img")[0].src = '{% static "icons/exclamation-triangle-fill.svg" %}';
  // }
  var title = "agent base URL: " + beatplayer_status.agent_base_url + ", reachable: " + beatplayer_status.reachable + ", registered: " + beatplayer_status.registered_at + ", mounted: " + beatplayer_status.mounted
  ele.find("img")[0].title = title;
});

socket.on('append_player_output', function(output) {
  $("#player_output").html((output.data.clear ? "" : $("#player_output").html()) + output.message);
  realignPage();
});

socket.on('alert', function(data){
  console.log(data);
  alert(data.message);
});

socket.on('message', function(data){
  console.log(data);
  showError(data);
  realignPage();
})
