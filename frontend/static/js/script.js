//-BUTTONS-FUNCTIONS------------------------------------------------------------

function start() {
    document.getElementById("start").disabled = true;
    document.getElementById("stop").disabled = false;
    document.getElementById("chargeState").innerHTML = "CHARGING";
    document.getElementById("chargeState").className = "orange";
}

function stop() {
    document.getElementById("start").disabled = false;
    document.getElementById("stop").disabled = true;
    document.getElementById("chargeState").innerHTML = "NOT CHARGING";
    document.getElementById("chargeState").className = "red";
}

//------------------------------------------------------------------------------

/*
    url: -- the url from which you want to request data
    path: - the missing part of the url
*/

function getRequest(url, path) {
    let headers = new Headers();

    headers.append('Content-Type', 'application/json');
    headers.append('Accept', 'application/json');

    headers.append('Access-Control-Allow-Origin', url);
    headers.append('Access-Control-Allow-Credentials', 'true');

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

/*
    json: ----- is the json that you would like to insert in the table

    table: ---- is the table you want to create (you can create a new one or
                use one already in the HTML code)
                REMEMBER TO ADD THE CLASS BEFORE PASSING IT

    container:  is the container that will contains the table to display it
*/

function createTable(json, table, container) {
    var col = [];
    for (var key in json[0]) {
        if (col.indexOf(key) === -1) {
            col.push(key);
        }
    }

    var thead = table.createTHead();
    var tr = thead.insertRow(-1)

    for (var i = 0; i < col.length; i++) {
        var th = document.createElement("th")
        th.innerHTML = col[i]
        tr.appendChild(th)
    }

    var tbody = table.createTBody();
    for (var i = 0; i < json.length; i++) {
        tr = tbody.insertRow(-1);

        for (var j = 0; j < col.length; j++) {
            var tabCell = tr.insertCell(-1);
            tabCell.innerHTML = json[i][col[j]];
        }
    }

    container.innerHTML = ""
    container.appendChild(table)
}

//------------------------------------------------------------------------------

/** Stores the reference to the elapsed time interval*/
var elapsedTimeIntervalRef;

/** Stores the start time of timer */
var startTime;

/** Starts the stopwatch */
function elapsedTime() {
    // Set start time based on whether the page has been refreshed or changed
    if (sessionStorage.getItem("startTime") == null) {
        startTime = new Date();
        sessionStorage.setItem("startTime", startTime);

    } else {
        startTime = new Date(sessionStorage.getItem("startTime"));
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
    getElapsedTime: function(startTime) {

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
