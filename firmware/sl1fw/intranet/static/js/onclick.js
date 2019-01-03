function hookOnClick() {
	var get_page = function() {
		return $("#page").data('page')
	}
	
	$(".click").mousedown(function() {
		ws.send(JSON.stringify({ 'page' : get_page(), 'id' : $(this).attr('id'), 'pressed' : true }));
	});
    $(".click").mouseup(function() {
		ws.send(JSON.stringify({ 'page' : get_page(), 'id' : $(this).attr('id'), 'pressed' : false }));
	});
}
