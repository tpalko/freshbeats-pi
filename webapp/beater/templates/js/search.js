$(document).on('keyup', 'form[id="search_form"] input', function(e){

	e.preventDefault();

	if($(this).val().length < 3){
		return;
	}

	$.ajax({

		url: '{% url "beater.views.get_search_results" %}',
		data: $(this).parent().serialize(),
		type: "GET",
		datatype: "json",
		success: function(data, textStatus, jqXHR){
			
			$("#search_results").html("");
			$("#search_results").append(data['artists']);
			$("#search_results").append(data['albums']);
			$("#search_results").append(data['songs']);
		}
	});

	return false;
});