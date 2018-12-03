var ws;

function wsInit() {

    // Connect to Web Socket
    ws = new WebSocket("ws://" + window.location.host + "/ws");

    // Set event handlers.
    ws.onopen = function() {
        document.body.innerHTML = "LOADING...";
    };

    ws.onmessage = function(e) {
        var data = JSON.parse(e.data);
        if (data.type == "page") {
            document.body.innerHTML = data.content;
            hookOnClick();
        } else if (data.type == "items") {
            var i;
            for (i in data.content) {
                $("#" + i).html(data.content[i])
            };
// TODO } else if data.type == "new" {
        } else {
            console.log("invalid dataType " + data.type)
        };
    };

    ws.onclose = function() {
        alert("Connection closed");
    };

    ws.onerror = function(e) {
        alert("Connection error");
        console.log(e)
    };

}
