function readlog() {

    var logFile = new XMLHttpRequest();
    logFile.open("GET", window.location.origin + "/logf", true);
    logFile.onreadystatechange = function() {
        var regex = new RegExp(document.getElementById("form").elements["regex"].value, 'g');
        if (logFile.readyState === 4) {
            if (logFile.status === 200) {
                lines = logFile.responseText.split("\n");
                var count = lines.length;
                var filtered = []
                for (var i = 0; i < count; i++) {
                    var line = lines[i]
                    if (regex.test(line)) {
                        filtered.push(line);
                    }
                }
                count = filtered.length;
                var text = "";
                for (var i = count > 256 ? count - 256 : 0; i < count; i++) {
                    text += filtered[i] + "\n";
                }
                log = document.getElementById("log");
                log.innerText = text;
                log.style.paddingTop = document.getElementById("control").offsetHeight + "px";

            }
        }
    }
    logFile.send(null);
}

//clearInterval(intervalId);

function copyRegex() {
    var formElements = document.getElementById("form").elements;
    formElements["regex"].value = formElements["text"].value;
}

function makeRegex() {
    var formElements = document.getElementById("form").elements;
    var regex = "";

    radios1 = formElements["severities"];
    var severities = []
    for (var i = 0, length = radios1.length; i < length; i++) {
        if (radios1[i].checked) {
            severities.push(radios1[i].value);
        }
    }

    radios2 = formElements["modules"];
    var modules = []
    for (var i = 0, length = radios2.length; i < length; i++) {
        if (radios2[i].checked) {
            modules.push(radios2[i].value);
        }
    }

    // ^(?:(?!DEBUG|INFO).)+$
    // (DEBUG|INFO)
    var severity = formElements["severity"].value;
    var module = formElements["module"].value;

    if (severity != "ignore" && severities.length) {
        if (formElements["severity"].value == "hide") {
            regex += "^(?:(?!" + severities.join("|") + ").)+";
            if (module == "ignore" || !modules.length) {
                regex += "$";
            }
        } else {
            regex += "(" + severities.join("|") + ")";
        };
    };

    if (module != "ignore" && modules.length) {
        if (formElements["module"].value == "hide") {
            if (severity == "ignore" || !severities.length) {
                regex += "^";
            }
            regex += "(?:(?!" + modules.join("|") + ").)+$";
        } else {
            if (severity == "show" && severities.length) {
                regex += ".*";
            }
            regex += "(" + modules.join("|") + ")";
        };
    };

    formElements["text"].value = regex;
}

function setAll(where) {
    radios = document.getElementById("form").elements[where];
    for (var i = 0, length = radios.length; i < length; i++) {
        radios[i].checked = true;
    }
}

function setNone(where) {
    radios = document.getElementById("form").elements[where];
    for (var i = 0, length = radios.length; i < length; i++) {
        radios[i].checked = false;
    }
}

function toggle(where) {
    radios = document.getElementById("form").elements[where];
    for (var i = 0, length = radios.length; i < length; i++) {
        radios[i].checked = !radios[i].checked;
    }
}
