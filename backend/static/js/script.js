/*
    url: -- the url from which you want to request data

    path: - the missing part of the url
*/

function getRequest(url, path) {
    let headers = new Headers();

    headers.append('Content-Type', 'application/json');
    headers.append('Accept', 'application/json');

    // must comment these two lines
    /*headers.append('Access-Control-Allow-Origin', url);
    headers.append('Access-Control-Allow-Credentials', 'true');*/

    headers.append('GET', 'POST', 'OPTIONS');

    //headers.append('Authorization', 'Basic ' + base64.encode(username + ":" + password));

    let request = new Request(url + path, {
        mode: 'same-origin',
        credentials: 'omit',
        method: 'GET',
        headers: headers
    });

    return request;
}

function postRequest(url, data) {
    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
            // 'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: data
    });
}

/*
    path: is the path (no url) of the assigned timer
*/

function deleteTimer(path) {
    for (let i = 0; i < timer.length; i++) {
        if (timer[i]["chart"] == path) {
            clearInterval(timer[i]["timer"]);
            timer.splice(i, 1);
            break;
        }
    }
}

/*
    form: the form to be listened

    path: if the command would be an action or a setting change
*/

function formListener(form, path) {
    form.addEventListener('submit', function (event) {
        event.preventDefault();                   // prevent page from refreshing
        //const formData = new FormData(form);    // grab the data inside the form fields
        let url = "command/" + path;

        let v = form.elements["value"].value.toLowerCase();
        let value = v == "true"? true : v == "false"? false : parseInt(v);

        j = {
            "com-type": form.elements["com-type"].value,
            "value": value
        };

        postRequest(url, JSON.stringify(j));
    });
}

function clearErrors() {
    let url = "command/action";

    let json = {
        "com-type": "latch-errors",
        "value": true
    }

    postRequest(url, JSON.stringify(json));
}

function updateSessionValue(key, value) {
    if(sessionStorage.getItem(key) == null || sessionStorage.getItem(key) != value) {
        sessionStorage.setItem(key, value);
    }
}

/*
    id: --- the item id

    key: -- the session attribute's key

    value:  the default value if the session value is NULL
*/

function uploadSessionValue(id, key, value) {
    let item = sessionStorage.getItem(key);

    if(item != null) {
        value = item;
    }
    document.getElementById(id).innerHTML = value; // value is passed as a default value
}

/*
    fc: ---- the fast charge button to update

    enabled: this parameter say if the Fast Charge is either enabled or disabled
*/

function uploadFCValue(fc, enabled) {
    if(enabled) {
        if(fc.classList.contains("btn-danger")) {
            fc.classList.remove("btn-danger");
            fc.className += " btn-success";
        }
    } else {
        if(fc.classList.contains("btn-success")) {
            fc.classList.remove("btn-success");
            fc.className += " btn-danger";
        }
    }
}

// this function update the header's value when the page is loaded, reading data from session attributes
function updateHeader() {
    for(let key in states) {
        let value = "0";
        if(key == "timeText") {
            value = "00:00";
        }
        if(key != "fc") {
            uploadSessionValue(key, states[key], value);
        } else {
            let fc = document.getElementById(key);
            let fcValue = sessionStorage.getItem("fcState");

            fcValue = fcValue == "true" ? true : false;
            uploadFCValue(fc, fcValue);
        }
    }
}
//-SETTINGS-FUNCTIONS-----------------------------------------------------------
/*
    sliderName: the id of the slider

    label: ---- the id of where you want to print the slider value
*/

function changeValue(sliderName, label) {
    let slider = document.getElementById(sliderName);
    let output = document.getElementById(label);

    let green = "#00ba44";
    let gray = "#d3d3d3";

    let value = (slider.value - slider.min) / (slider.max - slider.min) * 100; // adjust the left-side slider color
    slider.style.background = 'linear-gradient(to right, ' + green + ' 0%, ' + green + ' ' + value + '%, ' + gray + ' ' + value + '%, ' + gray + ' 100%)';

    output.innerHTML = slider.value;
}

/*
    enabled: a flag that says if the fastcharge is enabled or not
*/

function enableDisable(enabled) {
    let enableButton = document.getElementById("enable");
    let disableButton = document.getElementById("disable");

    // modify are sent by the formListener
    if(enabled) {                               // if fast charge isn't enabled
        enableButton.style.display = "none";    // hide the enable button
        disableButton.style.display = "inline"; // and show the disable button
    } else {                                    // if the fast charge has been enabled
        enableButton.style.display = "inline";  // show the enable button
        disableButton.style.display = "none";   // and hide the disabled button
    }
}
//-END-SETTINGS-FUNCTIONS-------------------------------------------------------
//-TIME-FUNCTIONS---------------------------------------------------------------

function elapsedTime(timeText, entered) {
    // Compute the elapsed time & display
    let text = timeAndDateHandling.getElapsedTime(entered) //pass the actual record start time
    updateSessionValue("timeText", text);
    timeText.innerHTML = text;
}

//API for time and date functions

var timeAndDateHandling = {
    /** Computes the elapsed time since the moment the function is called in the format mm:ss or hh:mm:ss
     * @param {String} startTime - start time to compute the elapsed time since
     * @returns {String} elapsed time in mm:ss format or hh:mm:ss format if elapsed hours are 0.
     */
    getElapsedTime: function (startTime) {

        // Record end time
        let endTime = new Date();

        // Compute time difference in milliseconds
        let timeDiff = endTime.getTime() - startTime.getTime();

        // Convert time difference from milliseconds to seconds
        timeDiff = timeDiff / 1000;

        // Extract integer seconds that dont form a minute using %
        let seconds = Math.floor(timeDiff % 60); //ignoring uncomplete seconds (floor)

        // Pad seconds with a zero if neccessary
        let secondsAsString = seconds < 10 ? "0" + seconds : seconds + "";

        // Convert time difference from seconds to minutes using %
        timeDiff = Math.floor(timeDiff / 60);

        // Extract integer minutes that don't form an hour using %
        let minutes = timeDiff % 60; //no need to floor possible incomplete minutes, becase they've been handled as seconds

        // Pad minutes with a zero if neccessary
        let minutesAsString = minutes < 10 ? "0" + minutes : minutes + "";

        // Convert time difference from minutes to hours
        timeDiff = Math.floor(timeDiff / 60);

        // Extract integer hours that don't form a day using %
        let hours = timeDiff % 24; //no need to floor possible incomplete hours, becase they've been handled as seconds

        // Convert time difference from hours to days
        timeDiff = Math.floor(timeDiff / 24);

        // The rest of timeDiff is number of days
        let days = timeDiff;

        let totalHours = hours + (days * 24); // add days to hours
        let totalHoursAsString = totalHours < 10 ? "0" + totalHours : totalHours + "";

        if (totalHoursAsString === "00") {
            return minutesAsString + ":" + secondsAsString;
        } else {
            return totalHoursAsString + ":" + minutesAsString + ":" + secondsAsString;
        }
    }
}

Number.prototype.padLeft = function(base,chr) {
    var  len = (String(base || 10).length - String(this).length)+1;
    return len > 0? new Array(len).join(chr || '0')+this : this;
}
// usage
//=> 3..padLeft() => '03'
//=> 3..padLeft(100,'-') => '--3'

function getDateFormat(date) {
    let timestamp = [(date.getMonth() + 1).padLeft(), date.getDate().padLeft(), date.getFullYear()].join("/") + " " +
                    [date.getHours().padLeft(), date.getMinutes().padLeft(), date.getSeconds().padLeft()].join(":");
    return timestamp;
}
//-END-TIME-FUNCTIONS-----------------------------------------------------------
