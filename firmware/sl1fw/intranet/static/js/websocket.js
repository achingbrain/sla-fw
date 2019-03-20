var ws;

function wsInit(dir) {
	/**
	 * Updates item value
	 * 
	 * Value can be button state (boolean), textual value. Textual values are
	 * set either to child element marked with value class or directly to the
	 * toplevel element marked by item identifier.
	 */
	update_item = function(id, data) {
		var element = $("#" + id);
		var value = element.find(".value")
		var btn = element.find(".btn.logic")
		 
		if(btn.length > 0) {
			// Set button logical state
			btn.toggleClass("active", data == 1)
		} else if (value.length > 0) {
			// Set value sub-element text
			value.text(data)
		} else {
			// Set whole element as html
			element.html(data)
		}
	};

	// Connect to Web Socket
	ws = new WebSocket("ws://" + window.location.host + "/" + dir);

	// Set event handlers.
	ws.onopen = function() {
		document.body.innerHTML = "LOADING...";
	};

	ws.onmessage = function(e) {
		var data = JSON.parse(e.data);
		console.log("Incoming WebSocket message: ", e, data)
		if (data.type == "page") {
			document.body.innerHTML = data.content;


			hookOnClick();
			$('input[type=checkbox][data-toggle^=toggle]').bootstrapToggle();
			hookLinkedControls();
			hookHiddenConnect();
			hookWifiConnect();
			hookWifiOff();
			hookFlash();
			hookTimeSet();
			hookShowAdmin();

		} else if (data.type == "items") {
			var i;
			for (i in data.content) {
				self.update_item(i, data.content[i])
			};
// TODO } else if data.type == "new" {
		} else {
			console.log("invalid dataType " + data.type)
		};
	};

	ws.onclose = function() {
		alert("Connection closed");
		location.reload();
	};

	ws.onerror = function(e) {
		alert("Connection error");
		console.log(e)
	};
	
}
