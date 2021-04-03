//-GET-THE-BMS-HV-STATUS--------------------------------------------------------
var url = 'http://127.0.0.1:5000';
var path = '/bms-hv/status';

request = getRequest(url, path);

fetch(request)
    .then(response => response.json())
    .then(json => {
        var b = document.getElementById("bmsState")

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
        let str = json[0][key].substr(6)    // to take STATE.[status]
        b.innerHTML = str                   // i.e. STATE.TS_OFF = TS_OFF

        switch (str) {
            case "TS_ON":
                b.className = "green"
                break;
            case "PRECHARGE":
                b.className = "orange"
                break;
            case "FATAL":
            case "TS_OFF":
                b.className = "red"
                break;
        }
    })
    .catch(error => console.log('Authorization failed : ' + error.message))
//-END-GET-THE-BMS-HV-STATUS----------------------------------------------------

//-GET-THE-HANDCART-STATUS------------------------------------------------------
//var url = 'http://127.0.0.1:5000';
var path = '/handcart/status';

request = getRequest(url, path);

fetch(request)
    .then(response => response.json())
    .then(json => {
        var b = document.getElementById("hcState")

        // if there's only one status message to read
        let key = "status"
        let str = json[0][key].substr(6)    // to take STATE.[status]
        b.innerHTML = str                   // i.e. STATE.TS_OFF = TS_OFF

        switch (str) {
            case "IDLE":
                b.className = "green"
                break;
            case "CHARGING":
                b.className = "orange"
                break;
            case "ERROR":
                b.className = "red"
                break;
        }
    })
    .catch(error => console.log('Authorization failed : ' + error.message))
//-END-GET-THE-HANDCART-STATUS--------------------------------------------------

//-GET-THE-BRUSA-STATUS---------------------------------------------------------
//var url = 'http://127.0.0.1:5000';
var path = '/brusa/status';

request = getRequest(url, path);

fetch(request)
    .then(response => response.json())
    .then(json => {
        var b = document.getElementById("brusaState")

        // if there's only one status message to read
        let key = "status"
        
    })
    .catch(error => console.log('Authorization failed : ' + error.message))
//-END-GET-THE-BRUSA-STATUS-----------------------------------------------------