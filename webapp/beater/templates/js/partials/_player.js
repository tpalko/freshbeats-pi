var player_url = '{% url "player" "null" %}';

function device_select(e) {
  
  var request = $.ajax({
    url: '{% url 'device_select' %}',
    data: {"device_id": e.target.value},
    type: "POST"
  });
  request.done(function( msg ) {
    
    // console.log('device select: ' + JSON.stringify(msg));
    
    old_device_id = $("#devices").attr('data-loaded');
    new_device_id = msg.data.device_id;

    $("#devices").attr('data-loaded', new_device_id);

    $("#beatplayer_status_" + old_device_id).hide();
    $("#beatplayer_status_" + new_device_id).show();

    log_client_presence({caller: "_player.js device_select done"});
  });
  request.fail(function( jqXHR, textStatus ) {
    showError(jqXHR);
  });
};

function mobile_select(e) {
  
  var request = $.ajax({
    url: '{% url 'mobile_select' %}',
    data: {"mobile_id": e.target.value},
    type: "POST"
  });
  request.done(function( msg ) {
    
    // console.log('mobile select: ' + JSON.stringify(msg));
    
    old_mobile_id = $("#mobiles").attr('data-loaded');
    new_mobile_id = msg.data.mobile_id;

    $("#mobiles").attr('data-loaded', new_mobile_id);

    $("#beatplayer_status_" + old_mobile_id).hide();
    $("#beatplayer_status_" + new_mobile_id).show();

    log_client_presence({caller: "_player.js mobile_select done"});
  });
  request.fail(function( jqXHR, textStatus ) {
    showError(jqXHR);
  });
};

function log_client_presence(args) {

  var request = $.ajax({
    url: '{% url 'log_client_presence' %}',
    data: args,
    type: "POST"
  });
  request.done(function( msg ) {
    console.log('log client response: ' + JSON.stringify(msg));
  });
  request.fail(function( jqXHR, textStatus ) {
    showError(jqXHR);
  });
};

var playlist_scrolled_at;

$(document).on('wheel', '.playlist', function(e) {
  playlist_scrolled_at = now;
})

$(document).on('change', '#device_select', device_select);
$(document).on('change', '#mobile_select', mobile_select);

$(function() {
  $("#device_select").trigger("change");
  $("#mobile_select").trigger("change");
  
  //TAG:MONITORING
  console.log("MONITORING ENABLED: {{ monitoring_enabled }}")
  if("{{ monitoring_enabled }}" == "True") {
    // console.error('MONITORING IS ENABLED BUT THE CALL IS COMMENTED _player.js line 86')
    console.log("monitoring enabled, initiating log_client_presence");
    setInterval(log_client_presence, 30000, {caller: "_player.js interval"});  
  } else {
    console.log("monitoring disabled");
  }
})

$(document).on('click', "a.player", function(e){

  var clickable = $(this);
  var command = $(this).attr("command");
        
  var albumid = $(this).attr("albumid");
  var songid = $(this).attr("songid");
  var artistid = $(this).attr("artistid");
  var playlistsongid = $(this).attr("playlistsongid");

  var url = player_url.replace(/null/, command);

  console.debug("Calling " + url)

  $.ajax({
    url: url,
    data: { albumid: albumid, songid: songid, artistid: artistid, playlistsongid: playlistsongid },
    type: "POST",
    datatype: "json",
    success: function(data, textStatus, jqXHR){
      var callback = $(clickable).attr('callback');
      if(callback != undefined){
        // console.log("Calling callback " + callback);
        // console.log("Sending:");
        console.log(data);
        fn = window[callback];
        fn(data);
      }
    }, 
    error: function(a, b, c) {
      console.log(a);
      console.log(b);
      console.log(c);
    }
  });

  return false;
});
