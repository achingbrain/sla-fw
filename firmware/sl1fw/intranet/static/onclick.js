function hookOnClick() {
    $(".click").mousedown(function() {
        ws.send(JSON.stringify({ 'page' : $("#page").text(), 'id' : $(this).attr('id'), 'pressed' : true }));
    });
    $(".click").mouseup(function() {
        ws.send(JSON.stringify({ 'page' : $("#page").text(), 'id' : $(this).attr('id'), 'pressed' : false }));
    });
}
