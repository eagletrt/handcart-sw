//------------------------------------------------------------------------------

/*
    url: -- the url from which you want to request data

    path: - the missing part of the url
*/

function getRequest(url, path) {
    let headers = new Headers();

    headers.append('Content-Type', 'application/json');
    headers.append('Accept', 'application/json');

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
    json: ----- is the json that you would like to insert in the table

    table: ---- is the table you want to create (you can create a new one or
                use one already in the HTML code)
                REMEMBER TO ADD THE CLASS BEFORE PASSING IT

    container:  is the container that will contains the table to display it
*/

function createTable(json, table, container) {
    let col = [];
    for (let key in json) {
        if (col.indexOf(key) === -1) {
            col.push(key);
        }
    }

    let thead = table.createTHead();
    let tr = thead.insertRow(-1);

    for (let i = 0; i < col.length; i++) {
        let th = document.createElement("th");
        th.innerHTML = col[i].charAt(0).toUpperCase() + col[i].slice(1);
        tr.appendChild(th);
    }

    let tbody = table.createTBody();

    let array = [];
    for (let i = 0; i < col.length; i++) {
        if (Array.isArray(json[col[i]])) {
            array = json[col[i]];
        }
    }

    for (let i = 0; i < array.length; i++) {
        tr = tbody.insertRow(-1);
        for (let j = 0; j < col.length; j++) {
            let tabCell = tr.insertCell(-1);
            let elem = json[col[j]];

            if (!Array.isArray(elem)) {
                tabCell.innerHTML = Date(elem);
            } else {
                tabCell.innerHTML = elem[i]["desc"];
            }
        }
    }

    container.innerHTML = "";
    container.appendChild(table);
}

/*
    path: - the path for the requested fetch

    id: --- the element's id in which write the value

    msg: -- standard message to write if there are no items
*/

function errorTable(path, id, msg) {
    //let url = 'http://127.0.0.1:5000';

    request = getRequest(url, path);

    fetch(request)
        .then(response => response.json())
        .then(json => {
            var container = document.getElementById("table-responsive-" + id);

            if (json["errors"].length > 0) {
                var table = document.createElement("table");
                table.className += "table table-striped table-sm";

                createTable(json, table, container);
            } else {
                container.innerHTML = msg;
            }
        })
        .catch(error => console.log('Authorization failed : ' + error.message))
}

/*
    path: - is the path (no url) of the assigned timer
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

//-SETTINGS-FUNCTIONS-----------------------------------------------------------
function onLoadEnableDisable() {
    (async () => { // syncronization is necessary
        //var url = 'http://127.0.0.1:5000';
        var path = '/command/setting';

        request = getRequest(url, path);

        let enabled;

        await fetch(request) // to sync
            .then(response => response.json())
            .then(json => {
                for (i = 0; i < json.length; i++) {
                    if (json[i]["com-type"] == "fast-charge") {
                        enabled = json[i]["value"];
                    }
                }
            })
            .catch(error => console.log('Authorization failed : ' + error.message))

        enableDisable(enabled);
    })();
}

/*
    json: ----- is the json that you would like to insert in the table

    table: ---- is the table you want to create (you can create a new one or
                use one already in the HTML code)
                REMEMBER TO ADD THE CLASS BEFORE PASSING IT

    container:  is the container that will contains the table to display it
*/

function enableDisable(enabled) {
    let enableButton = document.getElementById("enable");
    let disableButton = document.getElementById("disable");

    // modify are sent by the formListener
    if (enabled) {                              // if fast charge isn't enabled
        enableButton.style.display = "none";    // hide the enable button
        disableButton.style.display = "inline"; // and show the disable button
    } else {                                    // if the fast charge has been enabled
        enableButton.style.display = "inline";  // show the enable button
        disableButton.style.display = "none";   // and hide the disabled button
    }
}

/*
    form: - the form to be listened
*/

function formListener(form) {
    form.addEventListener('submit', function (event) {
        event.preventDefault();                 // prevent page from refreshing
        //const formData = new FormData(form);    // grab the data inside the form fields
        let url = '/command/setting/';

        j = {
            "com-type": form.elements["comType"].value,
            "value": form.elements["value"].value
        }

        console.log(JSON.stringify(j));

        postRequest(url, JSON.stringify(j));
    });
}

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

//------------------------------------------------------------------------------

/** Stores the reference to the elapsed time interval*/
var elapsedTimeIntervalRef;

/** Stores the start time of timer */
var startTime;

/** Stores the details of elapsed time when paused */
var pausedTime;

//-BUTTONS-FUNCTIONS------------------------------------------------------------

function onLoadStartStop() {
    // when page reloads I check if the time has been paused
    if (sessionStorage.getItem("paused") == "false") {                          // if no
        startStop(false);                                                       // I have to resume the timer
    } else if (sessionStorage.getItem("paused") == "true") {                    // if yes
        let tmpPausedTime = new Date(sessionStorage.getItem("pausedTime"));     // I have to restore the elapsed time
        let tmpTime = new Date();                                               // and print it in the time label
        tmpTime.setHours(tmpTime.getHours() - tmpPausedTime.getHours());
        tmpTime.setMinutes(tmpTime.getMinutes() - tmpPausedTime.getMinutes());
        tmpTime.setSeconds(tmpTime.getSeconds() - tmpPausedTime.getSeconds());

        document.getElementById("timeText").innerHTML = timeAndDateHandling.getElapsedTime(tmpTime)
    }
}

function startStop(started) {
    let startButton = document.getElementById("start");
    let stopButton = document.getElementById("stop");

    if (!started) {                             // if the timer has started
        let href = window.location.href;
        let re = /.*\/(.*)/;
        let page = href.match(re)[1];

        if (page == "") {                       // check if I am in the home page
            startButton.style.display = "none"; // hide the start button
            stopButton.style.display = "inline";// and show the stop button
        }

        elapsedTime();                          // then start the timer
    } else {                                    // if the timer haven't been started or it have been stopped
        startButton.style.display = "inline";   // show the start button
        stopButton.style.display = "none";      // and hide the stop button

        if (typeof elapsedTimeIntervalRef !== "undefined") {    // reset timer
            clearInterval(elapsedTimeIntervalRef);
            elapsedTimeIntervalRef = undefined;
        }

        sessionStorage.setItem("paused", true); // set the timer as paused

        pausedTime = new Date();
        pausedTime.setHours(pausedTime.getHours() - startTime.getHours());
        pausedTime.setMinutes(pausedTime.getMinutes() - startTime.getMinutes());
        pausedTime.setSeconds(pausedTime.getSeconds() - startTime.getSeconds());

        sessionStorage.setItem("pausedTime", pausedTime);   // save the elapsed time until paused
    }
}

/** Starts the stopwatch */
function elapsedTime() {
    // Set start time based on whether the page has been refreshed or changed
    //sessionStorage.setItem("startTime", "null");
    //sessionStorage.setItem("pausedTime", "null");
    if (sessionStorage.getItem("startTime") == null ||      // if it's the first time
        sessionStorage.getItem("startTime") == "null") {    // that I start the timer
        startTime = new Date();
        sessionStorage.setItem("startTime", startTime);     // save the start time

    } else if (sessionStorage.getItem("paused") == "true" &&            // if the timer has been paused
        (sessionStorage.getItem("pausedTime") != null &&          // and the paused timer has
            sessionStorage.getItem("pausedTime") != "null")) {       // been setted correctly
        pausedTime = new Date(sessionStorage.getItem("pausedTime"));    // save locally the elapsed time before the pause
        sessionStorage.setItem("paused", false);                        // remove the pause
        startTime = new Date();                                         // calculate the new start time
        // Subtract the elapsed hours, minutes and seconds from the current date
        // To get correct elapsed time to resume from it
        startTime.setHours(startTime.getHours() - pausedTime.getHours());
        startTime.setMinutes(startTime.getMinutes() - pausedTime.getMinutes());
        startTime.setSeconds(startTime.getSeconds() - pausedTime.getSeconds());

        sessionStorage.setItem("startTime", startTime);                 // save the new start time

    } else {    // if the timer hasn't been paused and the timer is running
        startTime = new Date(sessionStorage.getItem("startTime"));  // save locally the start time
    }

    // Every second
    elapsedTimeIntervalRef = setInterval(() => {
        // Compute the elapsed time & display
        document.getElementById("timeText").innerHTML = timeAndDateHandling.getElapsedTime(startTime) //pass the actual record start time
    }, 1000);
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
