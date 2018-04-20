socket.on('device_output', function(data){
	$("#device_output").html(data.out);
});

$(document).ready(function(){

	$.ajax({
		url: '{% url "device_report" %}',
		type: "GET",
		dataType: "json",
		success: function(data){
			console.log(data);
		}
	});
});