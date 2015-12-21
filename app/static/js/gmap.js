var map;
function initialize() {
 var mapOptions = {
   zoom: 2,
   center: new google.maps.LatLng(25, 0)
 };

 map = new google.maps.Map(document.getElementById('map-canvas'),
     mapOptions);

  {% set counter = 1 %}
  {% for marker in markers.keys() %}
    var marker{{ counter }} = new google.maps.Marker({
      position: new google.maps.LatLng({{ marker[0] }}, {{ marker[1] }}),
      map: map
    })

    var contentString = "<div id='container'><h4>Relays: {{ markers[marker] | length }}</h4>";
    {% for relay in markers[marker] %}
      contentString = contentString + "<p>{{ relay }}</p>";
    {% endfor %}
    contentString = contentString + "</div>";

    console.log(contentString);

    var infoWindow{{ counter }} = new google.maps.InfoWindow({
      content: contentString
    });

    google.maps.event.addListener(marker{{ counter }}, "click", function() {
      infoWindow{{counter}}.open(map, marker{{ counter }});
    });

    {% set counter = counter + 1 %}

  {% endfor %}
}

google.maps.event.addDomListener(window, 'load', initialize);
