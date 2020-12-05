var player_url = '{% url "player" "null" %}';

$(document).on('change', '#player_select', function(e) {
  $.ajax({
    url: '{% url 'player_select' %}',
    data: {"player_id": $(this).val()},
    type: "POST",
    success: function(data, textStatus, jqXHR) {
      console.log(data);
    }
  });
});

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
        fn = window[callback];
        fn(JSON.parse(data));
      }
    }
  });

  return false;
});
