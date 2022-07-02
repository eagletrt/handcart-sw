//-GET-THE-BMS-HV-STATUS--------------------------------------------------------

async function bmsStatus(path) {
    request = getRequest(url, path);

    var str = "";

    await fetch(request)
        .then(response => {
            if(!response.ok) {
                let state = document.getElementById("bmsState");

                state.innerHTML = "OFFLINE";
                state.className = "red";

                updateSessionValue("bmsState", "OFFLINE");
                updateSessionValue("car", null); // to hide cell and heat chart

                deleteTimer(path);

                throw new Error("Error code " + response.status + ": " + errMsg + " (BMS-HV)\n" + hintMsg);
            }
            return response.json();
        })
        .then(json => {
            //console.log("car: " + json);

            let state = document.getElementById("bmsState");

            let car = json["accumulator"];

            if(car == 1) {
                car = "Chimera";
            } else if (car == 2) {
                car = "Fenice";
            } else {
                car = "null";
            }

            updateSessionValue("car", car);

            let key = "status";
            str = json[key];

            updateSessionValue("bmsState", str);

            state.innerHTML = str;

            switch (str) {
                case "ON":
                case "OFF":
                    state.className = "green";
                    break;
                case "PRECHARGE":
                    state.className = "orange";
                    break;
                case "FATAL":
                case "OFFLINE":
                    state.className = "red";
                    break;
            }
        })
        .catch(error => console.log('Authorization failed : ' + error.message))
    return str;
}

{
    let t = setInterval(function () { // every 2 seconds
        ((async () => {
            let path = 'bms-hv/status';

            let element = {
                "timer": t,
                "chart": path
            }

            timer.push(element);

            bmsState = await bmsStatus(path);
        })());
    }, 2000);
}

async function bmsEW(path, field, timer) { // function to read the number of error(s)/warning(s)
    let bms = 0;

    let request = getRequest(url, path);

    await fetch(request)
        .then(response => {
            if(!response.ok) {
                //deleteTimer(timer);
                throw new Error("Error code " + response.status + ": " + errMsg + " (BMS-HV)\n" + hintMsg);
            }
            return response.json();
        })
        .then(json => {
            let s = json[field];

            if (s != undefined && s.length > 0) {
                bms = s.length;
            }
        })
        .catch(error => console.log('Authorization failed : ' + error.message))

    return bms;
}

//-END-GET-THE-BMS-HV-STATUS----------------------------------------------------
//-GET-THE-HANDCART-STATUS------------------------------------------------------
setInterval(function () { // every 2 seconds
    let path = 'handcart/status';

    request = getRequest(url, path);

    fetch(request)
        .then(response => {
            if(!response.ok) {
                throw new Error("Error code " + response.status + ": " + errMsg + " (HANDCART)");
            }
            return response.json();
        })
        .then(json => {
            let state = document.getElementById("hcState");

            let start = document.getElementById("start");
            let stop = document.getElementById("stop");
            let cancel = document.getElementById("cancel");
            let charge = document.getElementById("chargeBtn");
            let ok = document.getElementById("ok");

            // if there's only one status message to read
            let key = "state";
            let str = json[key];

            updateSessionValue("hcState", str);

            state.innerHTML = str;

            // get the actual path to check if there sould be buttons or not
            var href = window.location;

            var page = href.pathname.substring(1); // to remove the "/" before the page's name

            var buttons = false;

            if (page == "") { // check if I am in the home page
                buttons = true;
            }

            /*
            -CHECK: no start, no dati
            -IDLE: si start, si dati
            -PRECHARGE: bottone annulla - forse
            -READY: precharge completa, bottone diventa charge
            -CHARGE: il bottone diventa stop (torna allo stato ready)
            -C_DONE: carica completa, bottone OK
            */
            switch (str) {
                case "CHECK":
                    if (buttons) {
                        start.style.display = "none";
                        stop.style.display = "none";
                        cancel.style.display = "none";
                        charge.style.display = "none";
                        ok.style.display = "none";
                    }

                    state.className = "orange";
                    break;
                case "IDLE":
                    if (buttons) {
                        start.style.display = "inline";
                        stop.style.display = "none";
                        cancel.style.display = "none";
                        charge.style.display = "none";
                        ok.style.display = "none";
                    }

                    state.className = "green";
                    break;
                case "PRECHARGE":
                    if (buttons) {
                        start.style.display = "none";
                        stop.style.display = "none";
                        cancel.style.display = "inline";
                        charge.style.display = "none";
                        ok.style.display = "none";
                    }

                    state.className = "orange";
                    break;
                case "READY":
                    if (buttons) {
                        start.style.display = "none";
                        stop.style.display = "none";
                        cancel.style.display = "none";
                        charge.style.display = "inline";
                        ok.style.display = "none";
                    }

                    state.className = "green";
                    break;
                case "CHARGE":
                    if (buttons) {
                        start.style.display = "none";
                        stop.style.display = "inline";
                        cancel.style.display = "none";
                        charge.style.display = "none";
                        ok.style.display = "none";
                    }

                    let timeText = document.getElementById("timeText");
                    let entered = new Date(json["entered"]);
                    elapsedTime(timeText, entered);

                    state.className = "orange";
                    break;
                case "C_DONE":
                    if (buttons) {
                        start.style.display = "none";
                        stop.style.display = "none";
                        cancel.style.display = "none";
                        charge.style.display = "none";
                        ok.style.display = "inline";
                    }

                    state.className = "green";
                    break;
                case "ERROR":
                    if (buttons) {
                        start.style.display = "none";
                        stop.style.display = "none";
                        cancel.style.display = "none";
                        charge.style.display = "none";
                        ok.style.display = "none";
                    }

                    state.className = "red";
                    break;
            }
        })
        .catch(error => console.log('Authorization failed : ' + error.message))
}, 1000);
//-END-GET-THE-HANDCART-STATUS--------------------------------------------------
//-GET-THE-BRUSA-STATUS---------------------------------------------------------
async function brusaErrors(timer) {
    let errors = 0;

    let path = 'brusa/errors';

    let request = getRequest(url, path);

    await fetch(request)
        .then(response => {
            if(!response.ok) {
                //deleteTimer(timer);
                throw new Error("Error code " + response.status + ": " + errMsg + " (BRUSA)\n" + hintMsg);
            }
            return response.json();
        })
        .then(json => {
            let err = json["errors"];

            if (err != undefined && err.length > 0) {
                errors = err.length;
            }
        })
        .catch(error => console.log('Authorization failed : ' + error.message))

    return errors;
}

async function brusaWarnings(timer) {
    let warnings = 0;

    let path = 'brusa/status';

    let request = getRequest(url, path);

    await fetch(request)
        .then(response => {
            if(!response.ok) {
                //deleteTimer(timer);
                throw new Error("Error code " + response.status + ": " + errMsg + " (BRUSA)\n" + hintMsg);
            }
            return response.json();
        })
        .then(json => {
            let status = json["status"];

            if(status[IS_WARNING] == 1) {
                for(let w in WARNINGS) {
                    if(status[w] == 1) {
                        warnings++;
                    }
                }
            }
        })
        .catch(error => console.log('Authorization failed : ' + error.message))

    return warnings;
}

// these 2 function above can't be moved in the "script.js", else it won't work

{
    let t = setInterval(function () { // every 2 seconds
        ((async () => {
            let tName = 'ew';

            let element = {
                "timer": t,
                "chart": tName
            }

            timer.push(element);

            let brusaE = await brusaErrors(tName);     // get the number of brusa's errors
            let brusaW = await brusaWarnings(tName);   // get the number of brusa's warning

            let errors = 0;
            let warnings = 0;

            let state = document.getElementById("brusaState");
            let nWarn = document.getElementById("nWarnings");
            let nErr = document.getElementById("nErrors");

            if (brusaE > 0 || brusaW > 0) {             // check if there are errors or warnings
                if (brusaW > 0) {                       // if there are warnings
                    state.innerHTML = "WARNING";        // change the text
                    state.className = "orange";         // and the color

                    warnings += brusaW;           // then set the number of warnings
                }
                // even if there are warnings
                if (brusaE > 0) {                       // if there are errors
                    state.innerHTML = "ERROR";          // change the text
                    state.className = "red";            // and the color

                    errors += brusaE;            // then set the number of errors
                }
            } else {                                    // if there's no errors and warnings
                state.innerHTML = "IDLE";               // change the text
                state.className = "green";              // and the color
            }

            updateSessionValue("brusaState", state.innerHTML);

            //--------------------------------------------------------------------------------------------------------------
            let bmsErrors = await bmsEW("bms-hv/errors", "errors", tName);
            let bmsWarnings = await bmsEW("bms-hv/warnings", "warnings", tName);

            if (bmsErrors > 0) {
                errors += bmsErrors;
            }

            if (bmsWarnings > 0) {
                warnings += bmsWarnings;
            }

            updateSessionValue("errors", errors);
            updateSessionValue("warnings", warnings);

            nWarn.innerHTML = warnings;
            nErr.innerHTML = errors;
        })());
    }, 2000);
}
//-END-GET-THE-BRUSA-STATUS-----------------------------------------------------
//-GET-FASTCHARGE-STATUS--------------------------------------------------------
setInterval(function () { // every 2 seconds
    let path = 'command/setting';

    request = getRequest(url, path);

    fetch(request)
        .then(response => {
            if(!response.ok) {
                throw new Error("Error code " + response.status + ": " + errMsg + " (can't read settings)");
            }
            return response.json();
        })
        .then(json => {
            var fc = document.getElementById("fc");

            for (let i = 0; i < json.length; i++) {
                let com = json[i];
                if (com["com-type"] == "fast-charge") {
                    let enabled = com["value"];

                    updateSessionValue("fcState", enabled);

                    uploadFCValue(fc, enabled);

                    let href = window.location;

                    let page = href.pathname.substring(1); // to remove the "/" before the page's name

                    if(page == "settings") {
                        enableDisable(enabled);
                    }
                }
            }
        })
        .catch(error => console.log('Authorization failed : ' + error.message))
}, 2000);
//-END-GET-FASTCHARGE-STATUS----------------------------------------------------
//-GET-CUT-OFF-VOLTAGE----------------------------------------------------------
setInterval(function () { // every 2 seconds
    let path = 'command/setting';

    request = getRequest(url, path);

    fetch(request)
    .then(response => {
        if(!response.ok) {
            throw new Error("Error code " + response.status + ": " + errMsg + " (can't read settings)");
        }
        return response.json();
    })
        .then(json => {
            let cov = document.getElementById("COvolt");
            let mcoSlider = document.getElementById("MCOSlider"); // sliders
            let mciSlider = document.getElementById("MCISlider");
            let covSlider = document.getElementById("COSlider");
            // get the actual path to check if there sould be buttons or not
            var href = window.location;
            var page = href.pathname.substring(1); // to remove the "/" before the page's name

            for(let i = 0; i < json.length; i++) {
                let comType = json[i]["com-type"];
                let value = json[i]["value"];
                if(comType == "cutoff") {
                    cov.innerHTML = value;  // in the header
                    updateSessionValue("covValue", value);
                }
                if(page == "settings") {
                    if(comType == "max-out-current") {
                        mcoSlider.value = value;
                        updateSessionValue("mocValue", value);
                    } else if(comType == "max-in-current") {
                        mciSlider.value = value;
                        updateSessionValue("micValue", value)
                    } else if(comType == "cutoff") {
                        covSlider.value = value;
                    }
                }
            }
        })
        .catch(error => console.log('Authorization failed : ' + error.message))
}, 2000);
//-END-GET-CUT-OFF-VOLTAGE------------------------------------------------------
