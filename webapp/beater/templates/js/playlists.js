var spinner = new Spinner(spinner_opts).spin();

/*
  submit new playlist 
*/

function populate_playlists(data) {
  $("#playlists").html(data);
}

function load_playlists() {
  
  $("#overlay").append(spinner.el);
  
  $.ajax({
    url: '{% url "get_playlists" %}',
    type: "GET",
    success: function(data, textStatus, jqXHR) {
      if ($(data.body).find("option").length == 0) {
        $("#playlists").hide();
      } else {
        populate_playlists(data.body);
        load_playlistsongs();        
      }
      spinner.el.remove();
    }
  })
}

function load_playlistsongs() {

  var playlist_id = $("#playlist_select").val();
  
  if (playlist_id != undefined) {
    
    var playlistsongs_url = '{% url "get_playlistsongs" 0 %}';
    
    $("#overlay").append(spinner.el);
    
    $.ajax({
      url: playlistsongs_url.replace(/0/, playlist_id),
      type: "GET",
      success: function(data){
        $("#playlist_songs").html(data.body);
        $("#playlist_songs").attr('data-loaded', data.object.playlist_id);
        /*$("#playlistsong_sort").sortable();
        $(".draggable").draggable({ 
          "axis": "y",
          "connectToSortable": "#playlistsong_sort",
          stop: function(e, helper) {
            console.log(e);
            console.log(helper.position);
            console.log(helper.originalPosition);
            console.log(helper.offset);
            var ids = $(".draggable").map(function(i, e){ return e.id.split("_")[1]; });
            console.log(ids);
            $.ajax({
              url: '{% url "playlist_sort" %}',
              data: { thing: ids },
              type: "PUT",/?name=#
              dataType: 'json',
              success: function(data) {
                console.log(data);
              }
            });
          }
        });*/
        spinner.el.remove();
      }
    });  
  }
}

function new_playlist_prompt() {
  $("#new_playlist").hide();
  $("#new_playlist_form").show();
  $("#id_name").trigger('focus');
}

function submit_new_playlist(e) {
  e.preventDefault();
  var d = new FormData(this);
  $.ajax({
    url: '{% url "playlist" %}',
    type: "POST",
    data: { 'name': d.get('name'), 'auto_select': true },
    success: function(data, textStatus, jqXHR) {
      clearErrors();
      if (!data.success) {
        for (f in data.message) {
          showError(f + ": " + data.message[f]);          
        }
      } else {
        populate_playlists(data.body);
        // -- the DOM playlists will have a playlist selected 
        // -- if it's different than what is currently loaded, reload 
        if ($("#playlist_select").val() != $("#playlist_songs").data('loaded')) {
          load_playlistsongs();
        }
        $("#new_playlist_form").hide();
        $("#new_playlist").show();  
      }
    }
  });
  return false;
}

function playlist_select() {
  $.ajax({
    url: '{% url 'playlist_select' %}',
    data: {"playlist_id": $(this).val()},
    type: "POST",
    success: function(data, textStatus, jqXHR) {
      console.log(data);
    }
  });
};

$(document).on('change', '#playlist_select', playlist_select);
$(document).on("change", "#playlist_select", load_playlistsongs);

$(() => {
  
  load_playlists();

  $("#new_playlist").on("click", new_playlist_prompt);
  $("#new_playlist_form").on("submit", submit_new_playlist);  
});


