socket.on('device_output', function(data){
	$("#device_output").html(data.out);
});

var opts = {
  lines: 5 // The number of lines to draw
, length: 56 // The length of each line
, width: 5 // The line thickness
, radius: 84 // The radius of the inner circle
, scale: 0.25 // Scales overall size of the spinner
, corners: 1 // Corner roundness (0..1)
, color: '#000' // #rgb or #rrggbb or array of colors
, opacity: 0.25 // Opacity of the lines
, rotate: 18 // The rotation offset
, direction: 1 // 1: clockwise, -1: counterclockwise
, speed: 0.5 // Rounds per second
, trail: 100 // Afterglow percentage
, fps: 20 // Frames per second when using setTimeout() as a fallback for CSS
, zIndex: 2e9 // The z-index (defaults to 2000000000)
, className: 'spinner' // The CSS class to assign to the spinner
, top: '50%' // Top position relative to parent
, left: '50%' // Left position relative to parent
, shadow: false // Whether to render a shadow
, hwaccel: false // Whether to use hardware acceleration
, position: 'absolute' // Element positioning
}

$(document).ready(function(){

	var spinner = new Spinner(opts).spin();
	$("#remainder_overlay").append(spinner.el);

	$.ajax({
		url: '{% url "fetch_remainder_albums" %}',
		type: "GET",
		dataType: "json",
		success: function(data){
			$("#remainder_albums tbody").append(data.rows);
			$("#remainder_albums").dataTable({
				"paging": false,
				"columns": [
					{ "orderable": true, "width": "25%" },
					{ "orderable": true, "width": "20%"  },
					{ "orderable": false, "width": "15%"  },
					{ "orderable": true, "width": "15%"  },
					{ "orderable": false, "width": "15%"  },
					{ "orderable": false, "width": "10%"  },
				],
				"scrollY": "400px",
				"scrollX": true,
				"dom": 'ift'
			});
			spinner.el.remove();
		}
	})
});

$(document).on('click', '#apply_plan', function(e){

	e.preventDefault();

	$.ajax({
		url: $(this).attr("href"),
		type: "POST",
		dataType: "json",
		success: function(data){
			console.log(data);
		}
	});
});

$(document).on('click', '.album_cancel', function(e){

	e.preventDefault();

	$.ajax({
		url: $(this).attr("href"),
		type: "POST",
		dataType: "json",
		success: function (data){
			$("tr[data-id='" + data.album_id + "']").remove();

			if(data.state == 'checkedin'){
				$("#remainder_albums").append($(data.row));
			}else if(data.state == 'checkedout'){
				$("#checkedout_albums").append($(data.row));
			}			
		}
	});
});

$(document).on('click', '.album_checkin', function(e){

	e.preventDefault();

	$.ajax({
		url: $(this).attr("href"),
		type: "POST",
		dataType: "json",
		success: function (data){
			$("tr[data-id='" + data.album_id + "']").remove();
			$("#targeted_albums_checkin").append(data.row);
		}
	});
});

$(document).on('click', '.album_checkout', function(e){

	e.preventDefault();

	$.ajax({
		url: $(this).attr("href"),
		type: "POST",
		dataType: "json",
		success: function (data){
			$("tr[data-id='" + data.album_id + "']").remove();
			$("#targeted_albums_requestcheckout").append(data.row);
			$("#requestcheckout_size").html(data.requestcheckout_size);
		}
	});
});

var album_songs_url = "{% url "album_songs" 0 %}";

$(document).on('mouseover', '#remainder_albums td:nth-child(1)', function(e){

	e.preventDefault();

	var album_id = $(this).closest("tr").data('id');
	var row = $(this).closest("tr");

	if(row.attr("title") != undefined){
		return;
	}

	$.ajax({
		url: album_songs_url.replace(/0/, album_id),
		type: "GET",
		dataType: "json",
		success: function(data){
			$(row).attr("title", data);
		}
	});
});

