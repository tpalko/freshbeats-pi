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

$(document).on('submit', "form#new_album_form", function(e) {
  e.preventDefault();
  
  $.ajax({
    url: $(this).attr("action"),
    type: $(this).attr("method"),
    dataType: "json",
    data: $(this).serialize(),
    success: function(data, textStatus, jqXHR) {
      console.log(data);
      onAlbumAdd(data);
    },
    error: function(jqXHR, textStatus, errorThrown) {
      console.error(textStatus);
      console.error(errorThrown);
    }
  })
})

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

// TODO: get from query string, set cookie. if not in query string, get from cookie and set query string. if in neither, default false and set both.
// -- we want it in query string for bookmarking/sharing
// -- we want it in cookie for browsing to search/


let isRecordShopMode;

function setRecordShopMode(recordShopMode = false) {

	// isRecordShopMode = localStorage.getItem('isRecordShopMode') === 'true';
	isRecordShopMode = recordShopMode;
	$("#record_shop_mode").val(isRecordShopMode ? 1 : 0);
  console.log("isRecordShopMode:" + isRecordShopMode);
  if (isRecordShopMode) {
		$("button#record_shop_mode_btn")[0].innerText = 'Record Shop Mode';
	} else {
		$("button#record_shop_mode_btn")[0].innerText = 'Normal Search';
	}
}

$(document).on('click', "button[id='record_shop_mode_btn']", function(e) {
	// localStorage.setItem('isRecordShopMode', !isRecordShopMode);
	// isRecordShopMode = localStorage.getItem('isRecordShopMode') === 'true';
	setRecordShopMode(!isRecordShopMode);
	// -- TODO: do we want to re-search on mode toggle?
	perform_search();
	return false;
});

$(document).on('keyup', 'form[id="search_form"] input', function(e){
	e.preventDefault();
	perform_search();
	return false;
});

$(document).ready(() => {
	setRecordShopMode();

	// $("input#search").val("tr");
	// perform_search();
});

var searchjqXHR;

function perform_search() {

  var input_limit = $("#input_limit").val();
	if(!isRecordShopMode && $("input#search").val().length < input_limit){
		return;
	}
  
  if (searchjqXHR !== undefined) {
    console.log("aborting previous query..");
    searchjqXHR.abort();
  }

	searchjqXHR = $.ajax({
		url: '{% url "get_search_results" %}',
		data: $("form#search_form").serialize(),
		type: "POST",
		datatype: "json",
		success: function(data, textStatus, jqXHR){

			$("#search_results").html("");

			var keys = Object.keys(data);

			// if(isRecordShopMode) {
			// 	keys = keys.filter(key => key == 'artists');
			// }

      // -- if we didn't find anything in a category, say so
			$(keys.filter(key => data[key].length == 0))
				.each(function(i, key) {
					$("#search_results").append('<div>No ' + key + '</div>');
				});

			$(keys.filter( key => data[key].length > 0))
				.each(function(i, key) {
					$("#search_results").append("<div class='result_type_header_container'><h1 class='result_type_header'>" + key + "</h1></div>" + data[key]);
				});
      
      $(".result_type_header").each((i, h) => {
        type_headers[h.innerText] = { el: h, top: h.offsetTop };
      });
		}
	});  
}
