/*
    container: the id of the html table's container
*/
function createInfoTable(container) {
    const bInfo = {
        "NLG5_MC_ACT": "Actual mains current",
        "NLG5_MV_ACT": "Actual mains voltage",
        "NLG5_OC_ACT": "Output current to the battery",
        "NLG5_OV_ACT": "Actual battery output voltage",
        "NLG5_S_MC_M_CP": "Value of mains current limit",
        "NLG5_P_TMP": "Power stage temperature"
    };

    setInterval(function () { // every 2 seconds
        let path = 'brusa/info';

        request = getRequest(url, path);

        fetch(request)
            .then(response => {
                if(!response.ok) {
                    container.innerHTML = "Device not connected!";
                    throw new Error("Error code " + response.status + ": Device not connected (BRUSA)");
                }
                return response.json();
            })
            .then(json => {
                let id = "info-table";
                let table = document.getElementById(id);                // try to get the table

                if(table == null) {                                     // if the table doesn't exists
                    table = document.createElement("table");    // create a table
                    table.setAttribute("id", id);           // set its id as the "searched" id
                    table.className += "table table-striped";           // set the classes

                    let tbody = table.createTBody();
                    for(let k in json) {                                    // for every key in the json
                        if(k != "timestamp") {
                            let tr = tbody.insertRow(-1);
                            let td = document.createElement("td");
                            td.innerHTML = "<b>" + bInfo[k] + "</b>";       // print the key name in first column
                            tr.appendChild(td);

                            td = document.createElement("td");      // print the key's value in the second column
                            td.setAttribute("id", k);
                            td.innerHTML = json[k];
                            tr.appendChild(td);
                        }
                    }
                } else {                                            // if the table exists (already created)
                    for(let k in json) {
                        if(k != "timestamp") {
                            let td = document.getElementById(k);
                            td.innerHTML = json[k];                 // refresh the values with new ones
                        }
                    }
                }

                container.appendChild(table);
            })
            .catch(error => console.log('Authorization failed : ' + error.message))
    }, 2000);
}

/*
    json: ---- is the json that you would like to insert in the table

    table: --- is the table you want to create (you can create a new one or
                use one already in the HTML code)
                REMEMBER TO ADD THE CLASS BEFORE PASSING IT

    container: is the container that will contains the table to display it
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
    request = getRequest(url, path);
    let container = document.getElementById("table-responsive-" + id);

    fetch(request)
        .then(response => {
            if(!response.ok) {
                container.innerHTML = "Device not connected!";
                throw new Error("Error code " + response.status + ": Device not connected");
            }
            return response.json();
        })
        .then(json => {
            let errors = json["errors"];

            if (errors != undefined && errors.length > 0) {
                let table = document.createElement("table");
                table.className += "table table-striped table-sm";

                createTable(json, table, container);
            } else {
                container.innerHTML = msg;
            }
        })
        .catch(error => console.log('Authorization failed : ' + error.message))
}

/*
    path: ---- the path for the requested fetch

    container: is the container that will contains the table to display it

    msg: ----- standard message to write if there are no items
*/

function bmsWarningTable(path, container, msg) {
    request = getRequest(url, path);

    fetch(request)
        .then(response => {
            if(!response.ok) {
                container.innerHTML = "Device not connected!";
                throw new Error("Error code " + response.status + ": Device not connected (BMS-HV)");
            }
            return response.json();
        })
        .then(json => {
            if (json["warnings"].length > 0) {
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
    path: ---- the path for the requested fetch

    container: is the container that will contains the table to display it

    msg: ----- standard message to write if there are no items
*/

function brusaWarningTable(path, container, msg) {
    request = getRequest(url, path);

    fetch(request)
        .then(response => response.json())
        .then(json => {
            let status = json["status"];
            let warnings = [];
            for (let i = 0; i < status.length; i++) {
                let state = status[i]["pos"];
                if (state >= 8 && state <= 23) {
                    warnings.push(state);
                }
            }

            if (warnings.length > 0) {
                var table = document.createElement("table");
                table.className += "table table-striped table-sm";


                createTable(json, table, container);
            } else {
                container.innerHTML = msg;
            }
        })
        .catch(error => console.log('Authorization failed : ' + error.message))
}