$(document).ready(function(){

	var spinner = new Spinner(spinner_opts).spin();
	$("#manage_overlay").append(spinner.el);

	var manage_url = '{% url "fetch_manage_albums" %}';

	$.ajax({
		url: manage_url,
		type: "GET",
		dataType: "json",
		success: function(data){
			$("#manage_albums tbody").append(data.rows);
			$("#manage_albums").dataTable({
				"paging": false,
				"columns": [
					{ "orderable": true, "width": "25%" },
					{ "orderable": true, "width": "20%"  },
					{ "orderable": true, "width": "15%"  },
					{ "orderable": true, "width": "15%"  },
					{ "orderable": false, "width": "10%"  },
				],
				"scrollY": "600px",
				"scrollX": true,
				"dom": 'ift'
			});
			spinner.el.remove();
		}
	})
});

$(document).on('click', '.album_flag', function(e){

	e.preventDefault();

	$.ajax({
		url: $(this).attr("href"),
		type: "POST",
		dataType: "json",
		success: function (data){
			$("tr[data-id='" + data.album_id + "']").replaceWith(data.row);				
		}
	});
});
