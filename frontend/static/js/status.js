
    // GET THE ACCUMULATOR STATE
    var url = 'http://127.0.0.1:5000';
    var path = '/handcart/status';

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
            let key = "state"
            let str = json[0][key].substr(6)    // to take STATE.[status]
            b.innerHTML = str                   // i.e. STATE.IDLE = IDLE

            switch (str) {
                case "IDLE":
                    b.className = "green"
                    break;
                case "ERROR":
                    b.className = "red"
                    break;
            }
        })
        .catch(error => console.log('Authorization failed : ' + error.message))

    // GET THE BRUSA STATE
    //var url = 'http://127.0.0.1:5000';
    var path = '/bms/status';

    request = getRequest(url, path);

    fetch(request)
        .then(response => response.json())
        .then(json => {
            var b = document.getElementById("brusaState")

            // if there's only one status message to read
            let keyStatus = "status"
            let keyValue = "value"
            let keyVolts = "volts"

            let value1 = json[0][keyStatus][0][keyValue]
            let value2 = json[0][keyStatus][1][keyVolts]

            switch (true) {
                case value1 && value2:
                    b.innerHTML = "CONNECTED"
                    b.className = "green"
                    break;
                case (!value1 && value2):
                case (value1 && !value2):
                    b.innerHTML = "CONNECTING..."
                    b.className = "orange"
                    break;
                case !value1 && !value2:
                    b.innerHTML = "NOT CONNECTED"
                    b.className = "red"
                    break;
            }
        })
        .catch(error => console.log('Authorization failed : ' + error.message))
