$(document).ready(function(){

	var spinner = new Spinner(spinner_opts).spin();
	$("#overlay").append(spinner.el);
  
  $.ajax({
		url: '{% url "playlist" %}',
		type: "GET",
		success: function(data){
      $("#playlist").html(data);
      $("#playlistsong_sort").sortable();
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
            type: "PUT",
            dataType: 'json',
            success: function(data) {
              console.log(data);
            }
          });
        }
      });
      spinner.el.remove();
		}
  });
});
