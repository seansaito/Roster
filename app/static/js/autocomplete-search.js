var relays = []
$(function() {
  {% for relay in all_relays %}
  relays.push({
    value: '{{relay["fingerprint"] | safe}}' + "   (" + '{{relay["nickname"] | safe}}' + ")",
    data: '{{relay["fingerprint"] | safe}}'
  });
  {% endfor %}
  console.log(relays);
});
$("#autocomplete").autocomplete({
  lookup: relays,
  onSelect: function(selection) {
    window.location.replace(window.location.href + "family_detail/" + selection.data);
  }
});
