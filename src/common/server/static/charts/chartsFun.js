//-AMPERE-CHART-and-TEMP-CHART-and-VOLT-CHART-----------------------------------
function updateLineChartValue(chart, path, param, zoom, label) {
    let t = setInterval(function () {
        request = getRequest(url, path);

        fetch(request)
            .then(response => {
                if(!response.ok) {
                    //deleteTimer(path);
                    throw new Error("Error code " + response.status + ": " + errMsg + " (BMS-HV)\n" + hintMsg);
                }
                return response.json();
            })
            .then(json => {
                let timestamp = json["timestamp"];
                let d = json[param];

                if(zoom != NZ) {
                    let prevItem = chart.data[chart.data.length - 1];

                    let element = {
                        date: new Date(timestamp),
                        value: d
                    };

                    if (element.value >= prevItem.value) {
                        prevItem.color = am4core.color("green");
                    } else {
                        prevItem.color = am4core.color("red");
                    }

                    chart.addData(element);
                    chart.invalidateRawData();
                }

                let lbl = document.getElementById(label);

                if (lbl != null) {
                    lbl.innerHTML = d == undefined? 0 : d;
                    updateSessionValue(param, d);
                }
            })
            .catch(error => console.log('Authorization failed : ' + error.message))
    }, 2000);

    let element = {
        "timer": t,
        "chart": path
    }
    timer.push(element);
}

function updateMultilineChartValue(chart, path, param, zoom, label) {
    let t = setInterval(function () {
        request = getRequest(url, path);

        fetch(request)
            .then(response => {
                if(!response.ok) {
                    //deleteTimer(path);
                    throw new Error("Error code " + response.status + ": " + errMsg + " (BMS-HV)\n" + hintMsg);
                }
                return response.json()
            })
            .then(json => {
                let element = {};
                let prevItem = chart.data[chart.data.length - 1][param];
                let mainData;

                for(let key in json) {
                    if(key != "pack_voltage") {
                        let d = json[key];
                        if(key != "timestamp") {
                            element[key] = d;
                            if(key == param) {
                                mainData = d;
                                if(element[key] >= prevItem[key]) {
                                    prevItem.color = am4core.color("green");
                                } else {
                                    prevItem.color = am4core.color("red");
                                }
                            }
                        } else {
                            element["date"] = new Date(d);
                        }
                    }
                }

                chart.addData(element);
                chart.invalidateRawData();

                let lbl = document.getElementById(label);

                if (lbl != null) {
                    lbl.innerHTML = mainData == undefined? 0 : mainData;
                    updateSessionValue(param, mainData);
                }
            })
            .catch(error => console.log('Authorization failed : ' + error.message))
    }, 2000);

    let element = {
        "timer": t,
        "chart": path
    }
    timer.push(element);
}
//-END-AMPERE-CHART-and-TEMP-CHART-and-VOLT-CHART-------------------------------
//-CELL-CHART-------------------------------------------------------------------
function setColor(chart, series, max) {
    series.columns.template.adapter.add("fill", function (fill, target) {
        var i = target.dataItem.index;
        var perc = chart.data[i].voltage / max * 100;

        if (perc < 50) {
            r = 255;
            g = Math.round(5.1 * perc);
        } else {
            g = 255;
            r = Math.round(510 - 5.10 * perc);
        }
        b = 0;

        rgb = `rgb(${r}, ${g}, ${b})`;
        return rgb;
    });
}

function updateCellValue(chart, series) {
    setInterval(function () {
        var path = 'bms-hv/cells/voltage/last';

        request = getRequest(url, path);

        fetch(request)
            .then(response => response.json())
            .then(json => {
                am4core.array.each(chart.data, function (item) {
                    let i = parseInt(item["cell"]);
                    let cells = json["cells"];
                    console.log("Cell charge at index " + i + ": ")
                    console.log(cells[i])
                    let voltage = cells[i]["voltage"];

                    item.voltage = voltage;
                })

                chart.invalidateRawData();

                series.columns.each(function (column) {
                    column.fill = column.fill;
                })
            })
            .catch(error => console.log('Authorization failed : ' + error.message))
    }, 2000);
}
//-END-CELL-CHART---------------------------------------------------------------
//-HEAT-CHART-------------------------------------------------------------------
function setHeatColor(value) {
    let minValue = 0;
    let maxValue = 70 - minValue;
    let perc = 100 - ((value - minValue) / maxValue * 100);

    if (perc < 50) {
        r = 255;
        g = Math.round(5.1 * perc);
    } else {
        g = 255;
        r = Math.round(510 - 5.10 * perc);
    }
    b = 0;

    rgb = `rgb(${r}, ${g}, ${b})`;

    return rgb;
}

function getHeatData(cells, ncols) {
    let data = [];

    let value = 0;

    for (let i = 0; i < cells.length - 1; i++) {
        value = cells[i]["temp"];

        let x = i % ncols;
        let y = Math.floor(i / ncols);

        let element = {
            "x": x,
            "y": y,
            "color": setHeatColor(value),
            "value": value
        }

        data.push(element);
    }
    return data;
}

function updateHeatValue(chart, ncols) {
    setInterval(function () {
        var path = 'bms-hv/cells/temp/last';

        request = getRequest(url, path);

        fetch(request)
            .then(response => response.json())
            .then(json => {
                am4core.array.each(chart.data, function (item) {
                    let x = item.x;
                    let y = item.y;

                    let i = (x * ncols) + y;
                    
                    let cells = json["cells"];

                    console.log("Cell temp at index " + i + ": ")
                    console.log(cells[i])

                    let value = cells[i]["temp"];

                    item.value = value;

                    item.color = setHeatColor(value);

                    chart.invalidateData();
                })
            })
            .catch(error => console.log('Authorization failed : ' + error.message))
    }, 2000);
}
//-END-HEAT-CHART---------------------------------------------------------------
//-CHART-PAGE-------------------------------------------------------------------
function getCell(c) {
    if (divs < 2) {                                                 // compare max 2 charts
        divs++;                                                     // save how many charts there are

        let container = document.getElementById("chart");  // get the column container

        let mainRow = container.firstElementChild;
        if (mainRow == null) {                                      // check if a row has been already created
            mainRow = document.createElement("div");        // if not, it will create it
            mainRow.className = "row";
        }

        let mainCol = document.createElement("div");        // create the column that will contain the chart
        mainCol.className = "col-sm";
        mainCol.setAttribute("id", c);

        let buttonRow = document.createElement("div");      // create the close-button's row
        buttonRow.className = "row";

        let voidCol = document.createElement("div");
        voidCol.className = "col-sm-10";
        buttonRow.appendChild(voidCol);

        let buttonCol = document.createElement("div");      // create the colse-button's col
        buttonCol.className = "col-sm";

        let button = document.createElement("button");                          // create the button
        button.className = "btn";                                                       // set the close function with
        button.setAttribute("onclick", "reset(" + c + ", divs)");     // the parameter to close it
        button.innerHTML = "X";

        buttonCol.appendChild(button);

        buttonRow.appendChild(buttonCol);

        mainCol.appendChild(buttonRow);

        let chartRow = document.createElement("div");           // create the chart's row
        chartRow.className = "row";

        let chart = document.createElement("div");              // create the chart
        let id = "single" + c + "cell";                         // setup an id
        chart.setAttribute("id", id + "Chart");
        chart.className = "bigChart";

        chartRow.appendChild(chart);

        mainCol.appendChild(chartRow);

        mainRow.appendChild(mainCol);

        container.appendChild(mainRow);

        // call the chart creation
        createLineChart("bms-hv/cells?cell=" + c, id, "voltage", 15);
    } else {
        alert("You can compare max 2 charts at time!\nClose one of the opened or refresh the page to clean them all.");
    }
}

function reset(id) {
    if (divs > 0) {
        divs--;

        if (divs == 0) {                                         // if there are no more charts then remove also the row (graphical "issue")
            document.getElementById("chart").firstElementChild.remove();
        } else {
            let chartCol = document.getElementById(id);
            chartCol.remove();                                  // remove the whole column that contain the chart
        }

        let path = "bms-hv/cells/voltage/last?cell=" + id;
        deleteTimer(path);
    } else {
        alert("You shouldn't see the button...\nReport it!")
    }
}
//-END-CHART-PAGE---------------------------------------------------------------