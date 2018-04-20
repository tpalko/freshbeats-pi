function onAlbumAdd(data) {

	var album_name = data.album_name;
	var artist_id = data.artist_id;
	var album_id = data.album_id;

	var new_album = $("<div />")
		.attr("data-album_id", album_id)
		.text(album_name);

	var album_container = $("div#artist_" + String(artist_id) + "_album_container");

	$(data.row).appendTo(album_container);	
}

function onAlbumUpdate(data) {

	var album_id = data.album_id;
	var album_name = data.album_name;	

	$("[data-album_id='" + album_id + "']").text(album_name);
}

$(document).on('submit', "form#new_artist_form", function(e) {

	e.preventDefault();

	$.ajax({
		url: $(this).attr("action"),
		type: $(this).attr("method"),
		dataType: "json",
		data: $(this).serialize(),
		success: function(data, textStatus, jqXHR) {
			$(this).find("input").val("");
		},
		error: function(jqXHR, textStatus, errorThrown) {

		}
	});

	return false;
});

$(document).on('change', "input[type='checkbox'][id='record_shop_mode']", function(e) {

	perform_search();
});

$(document).on('keyup', 'form[id="search_form"] input', function(e){

	e.preventDefault();

	perform_search();

	return false;
});

function perform_search() {

	var record_shop_mode = $("form#search_form").find("[type='checkbox'][name='record_shop_mode']").is(':checked');

	if(!record_shop_mode && $("input#search").val().length < 3){
		return;
	}
	
	$.ajax({

		url: '{% url "get_search_results" %}',
		data: $("form#search_form").serialize(),
		type: "GET",
		datatype: "json",
		success: function(data, textStatus, jqXHR){
			
			$("#search_results").html("");

			var keys = Object.keys(data);

			if(record_shop_mode) {
				keys = keys.filter(key => key == 'artists');
			}

			$(keys.filter(key => data[key].length == 0))
				.each(function(i, key) {
					$("#search_results").append('<div>No ' + key + '</div>');
				});

			$(keys.filter( key => data[key].length > 0))				
				.each(function(i, key) {					
					$("#search_results").append(data[key]);
				});
		}
	});
}