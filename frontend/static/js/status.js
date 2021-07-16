//-GET-THE-BMS-HV-STATUS--------------------------------------------------------
var url = 'http://127.0.0.1:5000';
var path = '/bms-hv/status';

request = getRequest(url, path);

fetch(request)
    .then(response => response.json())
    .then(json => {
        let state = document.getElementById("bmsState")

        /*for (var key in json[0]) {
            if (key == "state") {
                var str = json[0][key].substr(6)
                b.innerHTML = str;

                switch (str) {
                    case "IDLE":
                        b.className = "green"
                        break;
                    case "ERROR":
                        b.className = "red"
                        break;
                }
            }
        }*/

        // if there's only one status message to read
        let key = "status"
        let str = json[key].substr(6)    // to take STATE.[status]
        state.innerHTML = str                // i.e. STATE.TS_OFF = TS_OFF

        switch (str) {
            case "TS_ON":
                state.className = "green"
                break;
            case "PRECHARGE":
                state.className = "orange"
                break;
            case "FATAL":
            case "TS_OFF":
                state.className = "red"
                break;
        }
    })
    .catch(error => console.log('Authorization failed : ' + error.message))
//-END-GET-THE-BMS-HV-STATUS----------------------------------------------------

//-GET-THE-HANDCART-STATUS------------------------------------------------------
//var url = 'http://127.0.0.1:5000';
path = '/handcart/status';

request = getRequest(url, path);

fetch(request)
    .then(response => response.json())
    .then(json => {
        let state = document.getElementById("hcState")

        let start = document.getElementById("start")
        let stop = document.getElementById("stop")
        let cancel = document.getElementById("cancel")
        let charge = document.getElementById("chargeBtn")
        let ok = document.getElementById("ok")

        // if there's only one status message to read
        let key = "status"
        let str = json[key].substr(6)    // to take STATE.[status]
        state.innerHTML = str            // i.e. STATE.TS_OFF = TS_OFF

        // get the actual path to check if there sould be buttons or not
        let href = window.location.href;
        let re = /.*\/(.*)/;
        let page = href.match(re)[1];

        var buttons = false

        if (page == "") {                       // check if I am in the home page
            buttons = true
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
                if(buttons) {
                    start.style.display = "none"
                    stop.style.display = "none"
                    cancel.style.display = "none"
                    charge.style.display = "none"
                    ok.style.display = "none"
                }

                state.className = "orange"
                // data can't be received
                break;
            case "IDLE":
                if(buttons) {
                    start.style.display = "inline"
                    stop.style.display = "none"
                    cancel.style.display = "none"
                    charge.style.display = "none"
                    ok.style.display = "none"
                }

                state.className = "green"
                break;
            case "PRECHARGE":
                if(buttons) {
                    start.style.display = "none"
                    stop.style.display = "none"
                    cancel.style.display = "inline"
                    charge.style.display = "none"
                    ok.style.display = "none"
                }

                state.className = "orange"
                break;
            case "READY":
                if(buttons) {
                    start.style.display = "none"
                    stop.style.display = "none"
                    cancel.style.display = "none"
                    charge.style.display = "inline"
                    ok.style.display = "none"
                }

                state.className = "green"
                break;
            case "CHARGE":
                if(buttons) {
                    start.style.display = "none"
                    stop.style.display = "inline"
                    cancel.style.display = "none"
                    charge.style.display = "none"
                    ok.style.display = "none"
                }

                state.className = "orange"
                break;
            case "C_DONE":
                if(buttons) {
                    start.style.display = "none"
                    stop.style.display = "none"
                    cancel.style.display = "none"
                    charge.style.display = "none"
                    ok.style.display = "inline"
                }

                state.className = "green"
                break;
            case "ERROR":
                state.className = "red"
                break;
        }
    })
    .catch(error => console.log('Authorization failed : ' + error.message))
//-END-GET-THE-HANDCART-STATUS--------------------------------------------------

//-GET-THE-BRUSA-STATUS---------------------------------------------------------
//var url = 'http://127.0.0.1:5000';
path = '/brusa/status';

request = getRequest(url, path);

fetch(request)
    .then(response => response.json())
    .then(json => {
        let state = document.getElementById("brusaState")

        // if there's only one status message to read
        let key = "status"

    })
    .catch(error => console.log('Authorization failed : ' + error.message))
//-END-GET-THE-BRUSA-STATUS-----------------------------------------------------

//-GET-CUT-OFF-VOLTAGE----------------------------------------------------------

setInterval(function () {
    path = '/command/settings';

    request = getRequest(url, path);

    fetch(request)
        .then(response => response.json())
        .then(json => {
            var b = document.getElementById("COvolt")

            for (i = 0; i < json.length; i++) {
                if(json[i]["com-type"] == "cutoff") {
                    b.innerHTML = json[i]["value"] + "V"
                }
            }
        })
        .catch(error => console.log('Authorization failed : ' + error.message))
}
, 2000);

// every 2 seconds or every time it has been changed

/*
path = '/command/settings';

request = getRequest(url, path);

fetch(request)
    .then(response => response.json())
    .then(json => {
        var b = document.getElementById("COvolt")

        for (i = 0; i < json.length; i++) {
            if(json[i]["com-type"] == "cutoff") {
                b.innerHTML = json[i]["value"] + "V"
            }
        }
    })
    .catch(error => console.log('Authorization failed : ' + error.message))
*/
//-END-GET-CUT-OFF-VOLTAGE------------------------------------------------------
