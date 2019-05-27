var get_page = function() {
    return $("#page").data('page')
}

function sendWebSocketEvent(pressed, id, data) {
    message = { 'page' : get_page(), 'id' : id, 'pressed' : pressed, 'data': data }
    console.log("Outgoing WebSocket message: ", message)
    ws.send(JSON.stringify(message));
}

function sendWebSocketAction(id, data) {
    sendWebSocketEvent(pressed = true, id = id, data = data)
    sendWebSocketEvent(pressed = false, id = id, data = data)
}

function hookOnClick() {
	var event = function(element, pressed) {
		data = {}
		$(".data").each(function(index) {
			id = $(this).attr('id')
			if(typeof id === typeof undefined) {
				id = $(this).attr('data-id')
			}

			// Try to read data-value attribute
			value = $(this).attr('data-value')

			// Try to read input value
			if (typeof value === typeof undefined && ( $(this).is('input') || $(this).is('select'))) {
				value = $(this).val()
			}

			// Finally try to read element text content
			if (typeof value === typeof undefined) {
				value = $(this).text()
			}

			data[id] = value
		})
		
		if($(element).hasClass("select")) {
			data['choice'] = $(element).attr('data-choice')
		}
		
		id = $(element).attr('id')
		if(typeof id === typeof undefined) {
			id = $(element).attr('data-id')
		}
		
		sendWebSocketEvent(pressed, id, data)
	}
	
	$(".click").mousedown(function() {
		event(this, true)
	});
    $(".click").mouseup(function() {
		event(this, false)
	});
}

function hookLinkedControls() {
    $('input[data-linked]').change(function() {
        checked = $(this).prop('checked')
        collapse = $(this).attr('data-linked-collapse')
        off = $(this).attr('data-linked-off')

        if(checked) {
            $(collapse).collapse('show')
            $(off).bootstrapToggle('off')
        } else {
            $(collapse).collapse('hide')
        }
    })
}

function hookHiddenConnect() {
    $('.hidden-connect').click(function() {
        // Collapse sibling items
        item = $(this).closest('.connection')
        item.siblings().find('.collapse').hide()

        // Show current item password prompt
        $(this).find('.collapse').show()
    })
    $('.hidden-connection').click(function() {
        item = $(this).data('connection-id')
        $(item).collapse('toggle')
    })
}

function hookWifiConnect() {
    $('.wifi-connect').click(function() {
        entry = $(this).closest('.wifi-ap-entry')

        // Obtain ssid
        ssid_element = $(entry).find('span.ssid')
        if(ssid_element.length > 0) {
            ssid = ssid_element.text()
        } else {
            ssid_element = $(entry).find('input.ssid')
            ssid= ssid_element.val()
        }

        // Read psk
        psk = $(entry).find('.psk').val()

        // Simulate click on button with ssid, psk data
        id = 'clientconnect'
        data = {
            'client-ssid': ssid,
            'client-psk': psk
        }
       sendWebSocketAction(id = id, data = data)
    })
}

function hookWifiOff() {
    $('#wifi-control').change(function() {
        checked = $(this).prop('checked')

        if(checked) {
            sendWebSocketAction(id = 'wifion')
        } else {
            sendWebSocketAction(id = 'wifioff')
        }
    })
}

function hookFlash() {
    $('#flash').click(function() {
        file = $('#fw_file').val()

        id = 'flash'
        data = {
            'firmware': file
        }
        sendWebSocketAction(id = id, data = data)
    })
}

function hookTimeSet() {
    // React to ntp/custom time switch changes
    $('#ntp-control').change(function() {
        checked = $(this).prop('checked')

        if(checked) {
            sendWebSocketAction(id = "ntpenable")
            $("#time-settings").collapse('hide')
        } else {
            sendWebSocketAction(id = "ntpdisable")
            $("#time-settings").collapse('show')
        }
    })

    // Set inital time setter values
    time_settings = $("#time-settings")
    unix_timestamp_sec = $('#unix_timestamp_sec').text()
    timezone = $('unix_timestamp_sec').data('timezone')

    date = new Date(unix_timestamp_sec * 1000);
    $('#hour').val(date.getHours())
    $('#minute').val(date.getMinutes())

    // Process time setter changes and store resulting timestamp
    $('#time-settings').find('select').change(function() {
        date = new Date(unix_timestamp_sec * 1000);
        date.setHours($('#hour').val())
        date.setMinutes($('#minute').val())

        $('#unix_timestamp_sec').text(date.getTime() / 1000)
    })


}

var clickCounter = 10;
function hookShowAdmin() {
    $('.hookShowAdmin').click(function() {
        clickCounter--;
        console.log(clickCounter);

        if(clickCounter < 1) {
          sendWebSocketAction("showadmin", {});
          clickCounter = 10;
        }
    })
}


function pad2(value) {
    if(value < 10) {
        return "0" + value
    } else {
        return "" + value
    }
}

function formatTime(date) {
    hours = date.getUTCHours()
    minutes = date.getUTCMinutes()

    return hours + "h " + minutes + "m"

}

function hookUpdate() {
    $('#progress').on('update', function(event, data) {
        $('#progress-bar').css('width', data + '%');
        $('#progress').text(data + "%");
    });

    $('#time_remain_min').on('update', function(event, data) {
        remaining = new Date(data * 1000 * 60);
        $(event.target).text(formatTime(remaining));

        now = new Date();
        end = new Date(now.getTime() + data * 1000 * 60);

        $('#estimated-end').text(pad2(end.getHours()) + ":" + pad2(end.getMinutes()));
    });

    $('#time_elapsed_min').on('update', function(event, data) {
        elapsed = new Date(data * 1000 * 60);
        $(event.target).text(formatTime(elapsed));
    });

    $('.update-fixed-2').on('update', function(event, data) {
        if (data != null) {
            $(event.target).text(data.toFixed(2));
        }
    });

    $('#current_layer').on('update', function(event, data) {
        if (data != null) {
            $(event.target).text(data);
        }

        function load() {
            $('#live').on('error', function() {
                console.log("Error loading live image, reloading in 1s")
                setTimeout(load, 1000)
            }).attr('src', "live.png?layer=" + data);
        }

        load()
    });
}