$(document).on('submit', 'form[id^="surveyalbum_"]', function(e){

  e.preventDefault();

  $.ajax({
    url: '{% url "survey_post" %}',
    data: $(this).serialize(),
    type: "POST",
    datatype: "json",
    success: function(data, textStatus, jqXHR){
      location = location;
    }
  });

  return false;
});
