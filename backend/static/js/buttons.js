/** Stores the reference to the elapsed time interval*/
var elapsedTimeIntervalRef;

/** Stores the start time of timer */
var startTime;

/** Stores the details of elapsed time when paused */
var pausedTime;

//-BUTTONS-FUNCTIONS------------------------------------------------------------

function onLoadCheckButtons() {
    // when page reloads I check if the time has been paused
    if (sessionStorage.getItem("paused") == "false") {                          // if no
        checkButtons(false);                                                       // I have to resume the timer
    } else if (sessionStorage.getItem("paused") == "true") {                    // if yes
        let tmpPausedTime = new Date(sessionStorage.getItem("pausedTime"));     // I have to restore the elapsed time
        let tmpTime = new Date();                                               // and print it in the time label
        tmpTime.setHours(tmpTime.getHours() - tmpPausedTime.getHours());
        tmpTime.setMinutes(tmpTime.getMinutes() - tmpPausedTime.getMinutes());
        tmpTime.setSeconds(tmpTime.getSeconds() - tmpPausedTime.getSeconds());

        document.getElementById("timeText").innerHTML = timeAndDateHandling.getElapsedTime(tmpTime)
    }
}

function checkButtons(started) {
    let startButton = document.getElementById("start");
    let stopButton = document.getElementById("stop");
    let cancelButton = document.getElementById("cancel");
    let chargeButton = document.getElementById("chargeBtn");
    let okButton = document.getElementById("ok");

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
