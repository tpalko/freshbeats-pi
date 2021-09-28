var player_url = '{% url "player" "null" %}';

function device_select(e) {
  
  var request = $.ajax({
    url: '{% url 'device_select' %}',
    data: {"device_id": e.target.value},
    type: "POST"
  });
  request.done(function( msg ) {
    
    console.log('device select: ' + JSON.stringify(msg));
    
    old_device_id = $("#devices").attr('data-loaded');
    new_device_id = msg.data.device_id;

    $("#devices").attr('data-loaded', new_device_id);

    $("#beatplayer_status_" + old_device_id).hide();
    $("#beatplayer_status_" + new_device_id).show();

    log_client_presence();
  });
  request.fail(function( jqXHR, textStatus ) {
    showError(jqXHR);
  });
};

function log_client_presence(e) {
  
  var request = $.ajax({
    url: '{% url 'log_client_presence' %}',
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

$(function() {
  $("#device_select").trigger("change");  
  setInterval(log_client_presence, 30000);  
})

$(document).on('click', "a.player", function(e){

  var clickable = $(this);
  var command = $(this).attr("command");
        
  var albumid = $(this).attr("albumid");
  var songid = $(this).attr("songid");
  var artistid = $(this).attr("artistid");
  var playlistsongid = $(this).attr("playlistsongid");

  var url = player_url.replace(/null/, command);

  $.ajax({
    url: url,
    data: { albumid: albumid, songid: songid, artistid: artistid, playlistsongid: playlistsongid },
    type: "POST",
    datatype: "json",
    success: function(data, textStatus, jqXHR){
      var callback = $(clickable).attr('callback');
      if(callback != undefined){
        console.log("Calling callback " + callback);
        console.log("Sending:");
        console.log(data);
        fn = window[callback];
        fn(data);
      }
    }
  });

  return false;
});
