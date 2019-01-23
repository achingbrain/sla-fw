var get_page = function() {
    return $("#page").data('page')
}

function sendWebSocketEvent(pressed, id, data) {
    message = { 'page' : get_page(), 'id' : id, 'pressed' : pressed, 'data': data }
    console.log("Outgoing WebSocket message: ", message)
    ws.send(JSON.stringify(message));
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
			if (typeof value === typeof undefined && $(this).is('input')) {
				value = $(this).val()
			}

			// Finally try to read element text content
			if (typeof value === typeof undefined) {
				value = $(this).text()
			}

			console.log(value)
			
			data[id] = value
		})
		
		if($(element).hasClass("select")) {
			data['choice'] = $(element).attr('data-choice')
		}
		
		id = $(element).attr('id')
		if(typeof id === typeof undefined) {
			id = $(element).attr('data-id')
		}
		
		console.log("data: ", data)
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
        console.log('Toggle: ' + $(this).prop('checked'))

        checked = $(this).prop('checked')
        collapse = $(this).attr('data-linked-collapse')
        off = $(this).attr('data-linked-off')

        console.log(checked, collapse, off)

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
        item = $(this).closest('.list-group-item')
        item.siblings().find('.collapse').hide()

        // Show current item password prompt
        $(this).find('.collapse').show()
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
        sendWebSocketEvent(pressed = true, id = id, data = data)
        sendWebSocketEvent(pressed = false, id = id, data = data)
    })
}

function hookWifiBothOffCheck() {
    $('#client-settings-control,#ap-settings-control').change(function() {
        client_checked = $('#client-settings-control').prop('checked')
        ap_checked = $('#ap-settings-control').prop('checked')

        if(!client_checked && !ap_checked) {
            // Simulate click on button with ssid, psk data
            id = 'wifioff'
            sendWebSocketEvent(pressed = true, id = id)
            sendWebSocketEvent(pressed = false, id = id)
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
        sendWebSocketEvent(pressed = true, id = id, data = data)
        sendWebSocketEvent(pressed = false, id = id, data = data)
    })
}