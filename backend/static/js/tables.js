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
                    throw new Error("Error code " + response.status + ": Device not connected (BRUSA)");
                }
                return response.json();
            })
            .then(json => {
                let id = "info-table";
                let table = document.getElementById(id);

                if(table == null) {
                    table = document.createElement("table");
                    table.setAttribute("id", id);
                    table.className += "table table-striped";

                    let tbody = table.createTBody();
                    for(let k in json) {
                        if(k != "timestamp") {
                            let tr = tbody.insertRow(-1);
                            let td = document.createElement("td");
                            td.innerHTML = "<b>" + bInfo[k] + "</b>";
                            tr.appendChild(td);

                            td = document.createElement("td");
                            td.setAttribute("id", k);
                            td.innerHTML = json[k];
                            tr.appendChild(td);
                        }
                    }
                } else {
                    for(let k in json) {
                        if(k != "timestamp") {
                            let td = document.getElementById(k);
                            td.innerHTML = json[k];
                        }
                    }
                }

                container.appendChild(table);
            })
            .catch(error => console.log('Authorization failed : ' + error.message))
    }, 2000);
}