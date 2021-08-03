//var url = 'http://10.196.172.17:8080';
//-GET-THE-BMS-HV-STATUS--------------------------------------------------------
var path = '/bms-hv/status';

request = getRequest(url, path);

fetch(request)
    .then(response => response.json())
    .then(json => {
        let state = document.getElementById("bmsState");

        // if there's only one status message to read
        let key = "status";
        str = json[key];
        //let str = json[key].substr(6);  // to take STATE.[status]
        state.innerHTML = str;          // i.e. STATE.TS_OFF = TS_OFF

        switch (str) {
            case "ON":
                state.className = "green";
                break;
            case "PRECHARGE":
                state.className = "orange";
                break;
            case "FATAL":
            case "OFF":
                state.className = "red";
                break;
        }
    })
    .catch(error => console.log('Authorization failed : ' + error.message))

async function bmsStatus(path, field) {
    let bms = 0;

    let request = getRequest(url, path);

    await fetch(request)
        .then(response => response.json())
        .then(json => {
            let s = json[field];

            if (s.length > 0) {
                bms = s.length;
            }
        })
        .catch(error => console.log('Authorization failed : ' + error.message))

    return bms;
}

((async () => {
    let errors = await bmsStatus("/bms-hv/errors", "errors");
    let warnings = await bmsStatus("/bms-hv/warnings", "warnings");

    if (errors > 0) {
        let nErr = document.getElementById("nErrors");
        nErr.innerHTML = parseInt(nErr.innerHTML) + errors; // then set the number of warnings
    }

    if (warnings > 0) {
        let nWarn = document.getElementById("nWarnings");
        nWarn.innerHTML = parseInt(nWarn.innerHTML) + warnings;
    }
})());

//-END-GET-THE-BMS-HV-STATUS----------------------------------------------------
//-GET-THE-HANDCART-STATUS------------------------------------------------------
path = '/handcart/status';

request = getRequest(url, path);

fetch(request)
    .then(response => response.json())
    .then(json => {
        let state = document.getElementById("hcState");

        let start = document.getElementById("start");
        let stop = document.getElementById("stop");
        let cancel = document.getElementById("cancel");
        let charge = document.getElementById("chargeBtn");
        let ok = document.getElementById("ok");

        // if there's only one status message to read
        let key = "status";
        let str = json[key].substr(6);   // to take STATE.[status]
        state.innerHTML = str;           // i.e. STATE.TS_OFF = TS_OFF

        // get the actual path to check if there sould be buttons or not
        let href = window.location.href;
        let re = /.*\/(.*)/;
        let page = href.match(re)[1];

        var buttons = false;

        if (page == "") {                       // check if I am in the home page
            buttons = true;
        }

        /*
        -CHECK: no start, no dati
        -IDLE: si start, si dati
        -PRECHARGE: bottone annulla
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
//-END-GET-THE-HANDCART-STATUS--------------------------------------------------
//-GET-THE-BRUSA-STATUS---------------------------------------------------------
async function brusaErrors() {
    let errors = 0;

    let path = '/brusa/errors';

    let request = getRequest(url, path);

    await fetch(request)
        .then(response => response.json())
        .then(json => {
            let err = json["errors"];

            if (err.length > 0) {
                errors = err.length;
            }
        })
        .catch(error => console.log('Authorization failed : ' + error.message))

    return errors;
}

async function brusaWarnings() {
    let warnings = 0;

    let path = '/brusa/status';

    let request = getRequest(url, path);

    await fetch(request)
        .then(response => response.json())
        .then(json => {
            let status = json["status"];

            for (let i = 0; i < status.length; i++) {
                if (status[i]["pos"] >= 8 && status[i]["pos"] <= 23) { // find warnings in the brusa status (code 8-23)
                    warnings++;
                }
            }
        })
        .catch(error => console.log('Authorization failed : ' + error.message))

    return warnings;
}

// these 2 function above can't be moved in the "script.js", else it won't work

((async () => {
    let errors = await brusaErrors();       // get the number of brusa's errors
    let warnings = await brusaWarnings();   // get the number of brusa's warning

    let state = document.getElementById("brusaState");

    if (errors > 0 || warnings > 0) {        // check if there are errors or warnings
        if (warnings > 0) {                  // if there are warnings
            state.innerHTML = "WARNING";    // change the text
            state.className = "orange";     // and the color

            let nWarn = document.getElementById("nWarnings");
            nWarn.innerHTML = parseInt(nWarn.innerHTML) + warnings; // then set the number of warnings
        }
        // even if there are warnings
        if (errors > 0) {                    // if there are errors
            state.innerHTML = "ERROR";      // change the text
            state.className = "red";        // and the color

            let nErr = document.getElementById("nErrors");
            nErr.innerHTML = parseInt(nErr.innerHTML) + errors; // then set the number of errors
        }
    } else {                                // if there's no errors and warnings
        state.innerHTML = "IDLE";           // change the text
        state.className = "green";          // and the color
    }
})());
//-END-GET-THE-BRUSA-STATUS-----------------------------------------------------
//-GET-CUT-OFF-VOLTAGE----------------------------------------------------------
setInterval(function () { // every 2 seconds or every time it has been changed
        path = '/command/setting';

        request = getRequest(url, path);

        fetch(request)
            .then(response => response.json())
            .then(json => {
                var cov = document.getElementById("COvolt");

                for (let i = 0; i < json.length; i++) {
                    if (json[i]["com-type"] == "cutoff") {
                        cov.innerHTML = json[i]["value"] + "V";
                    }
                }
            })
            .catch(error => console.log('Authorization failed : ' + error.message))
    }
    , 2000);
//-END-GET-CUT-OFF-VOLTAGE------------------------------------------------------
