$(document).on('click', '#select_albums_for_checkout', function(e){

	e.preventDefault();

	$.ajax({
		url: $(this).attr("href"),
		type: "GET",
		dataType: "json",
		success: function(data){
			console.log(data);
		}
	});
});