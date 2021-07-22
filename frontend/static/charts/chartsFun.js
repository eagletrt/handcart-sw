//-AMPERE-CHART-----------------------------------------------------------------
function updateAmpereValue(chart, series) {
    setInterval(function () {
        var url = 'http://127.0.0.1:5000';
        var path = '/bms-hv/ampere/last';

        request = getRequest(url, path);

        fetch(request)
            .then(response => response.json())
            .then(json => {
                timestamp = json["timestamp"]
                amp = json["amperes"]
                element = {
                    date: new Date(timestamp),
                    value: amp
                }
                chart.addData(element, 1);
                document.getElementById("amp").innerHTML = amp + "A";
            })
            .catch(error => console.log('Authorization failed : ' + error.message))
    }, 2000);
}
//-END-AMPERE-CHART-------------------------------------------------------------
//-CELL-CHART-------------------------------------------------------------------
function updateCellValue(chart, series) {
    setInterval(function () {
        var url = 'http://127.0.0.1:5000';
        var path = '/bms-hv/cells/last';

        request = getRequest(url, path);

        fetch(request)
            .then(response => response.json())
            .then(json => {
                am4core.array.each(chart.data, function (item) {
                    let i = parseInt(item["cell"]) - 1;
                    let cells = json["cells"];
                    let voltage = cells[i]["voltage"];

                    item.voltage = voltage;
                })

                chart.invalidateRawData();

                series.columns.each(function(column) {
                    column.fill = column.fill;
                })
            })
            .catch(error => console.log('Authorization failed : ' + error.message))
    }, 2000);
}
//-END-CELL-CHART---------------------------------------------------------------
//-HEAT-CHART-------------------------------------------------------------------
function setHeatColor(value) {
    let minValue = 20;
    let maxValue = 250-minValue;
    let perc = 100-((value-minValue)/maxValue*100);

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

function updateHeatValue(chart, series, nrows) {
    setInterval(function() {
        var url = 'http://127.0.0.1:5000';
        var path = '/bms-hv/heat';

        request = getRequest(url, path);

        fetch(request)
            .then(response => response.json())
            .then(json => {
                am4core.array.each(chart.data, function(item) {
                    let x = item.x;
                    let y = item.y;
                    let i = parseInt((x-1)*nrows + (y-1));

                    let cell = json["data"][i];
                    let value = cell["temp"];

                    item.value = value;

                    item.color = setHeatColor(value);

                    chart.invalidateData();
                })
            })
            .catch(error => console.log('Authorization failed : ' + error.message))
    }, 2000);
}

function updateHeatAvgValue(chart, series, nrows, p) {
    setInterval(function() {
        var url = 'http://127.0.0.1:5000';
        var path = '/bms-hv/heat';

        request = getRequest(url, path);

        fetch(request)
            .then(response => response.json())
            .then(json => {
                am4core.array.each(chart.data, function(item) {
                    let x = item.x;
                    let y = item.y;

                    let k = parseInt((x-1)*nrows + (y-1));

                    let value = 0;
                    let cells = json["data"];

                    for(let i = k * p; i < ((k * p) + p); i++) {
                        value += cells[i]["temp"];
                    }

                    value /= p;

                    item.value = value;

                    item.color = setHeatColor(value);

                    chart.invalidateData();
                })
            })
            .catch(error => console.log('Authorization failed : ' + error.message))
    }, 2000);
}
//-END-HEAT-CHART---------------------------------------------------------------
//-TEMP-CHART-------------------------------------------------------------------
function updateTempValue(chart, series) {
    setInterval(function () {
        var url = 'http://127.0.0.1:5000';
        var path = '/bms-hv/temp/last';

        request = getRequest(url, path);

        fetch(request)
            .then(response => response.json())
            .then(json => {
                timestamp = json["timestamp"]
                temp = json["temp"]
                element = {
                    date: new Date(timestamp),
                    value: temp
                }
                chart.addData(element, 1);
                document.getElementById("temp").innerHTML = temp + "°";
            })
            .catch(error => console.log('Authorization failed : ' + error.message))
    }
    , 2000);
}
//-END-TEMP-CHART---------------------------------------------------------------
//-VOLT-CHART-------------------------------------------------------------------
function updateVoltValue(chart, series) {
    setInterval(function () {
        var url = 'http://127.0.0.1:5000';
        var path = '/bms-hv/volt/last';

        request = getRequest(url, path);

        fetch(request)
            .then(response => response.json())
            .then(json => {
                timestamp = json["timestamp"]
                volt = json["volts"]
                element = {
                    date: new Date(timestamp),
                    value: volt
                }
                chart.addData(element, 1);
                document.getElementById("volt").innerHTML = volt + "V"; // insert the value in the top bar

                /*let coVolt = parseInt(document.getElementById("COvolt").innerHTML);
                let value = parseInt(100*volt/coVolt);
                document.getElementById("charge").innerHTML = value + "%";*/ // calculate the value of the charge
            })
            .catch(error => console.log('Authorization failed : ' + error.message))
    }
    , 2000);
}
//-END-VOLT-CHART---------------------------------------------------------------
