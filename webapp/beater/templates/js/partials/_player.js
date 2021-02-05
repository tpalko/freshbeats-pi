var player_url = '{% url "player" "null" %}';

function device_select() {
  $.ajax({
    url: '{% url 'device_select' %}',
    data: {"device_id": $(this).val()},
    type: "POST",
    success: function(data, textStatus, jqXHR) {
      console.log(data);
    }
  });
};

var playlist_scrolled_at;

$(document).on('wheel', '.playlist', function(e) {
  playlist_scrolled_at = now;
})

$(document).on('change', '#device_select', device_select);

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
