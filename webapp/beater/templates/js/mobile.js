socket.on('device_output', function(data){
	$("#device_output").html(data.out);
});

$(document).ready(function(){

	var spinner = new Spinner(spinner_opts).spin();
	$("#remainder_overlay").append(spinner.el);

	var remainder_url = '{% url "fetch_remainder_albums" %}';

	console.log("fetching: " + remainder_url);
	
	$.ajax({
		url: remainder_url,
		type: "GET",
		dataType: "json",
		success: function(data){
			$("#remainder_albums tbody").append(data.rows);
			$("#remainder_albums").dataTable({
				"paging": false,
				"columns": [
					{ "orderable": true, "width": "25%" },
					{ "orderable": true, "width": "20%"  },
					{ "orderable": true, "width": "15%"  },
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
