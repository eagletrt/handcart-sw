//-AMPERE-CHART-and-TEMP-CHART-and-VOLT-CHART-----------------------------------
function updateLineChartValue(chart, series, path, param, label, u) {
    var url = 'http://127.0.0.1:5000';

    let t = setInterval(function () {
        request = getRequest(url, path);

        fetch(request)
            .then(response => response.json())
            .then(json => {
                timestamp = json["timestamp"];
                d = json[param];

                prevItem = chart.data[chart.data.length-1];

                element = {
                    date: new Date(timestamp),
                    value: d
                };

                if(element.value > prevItem.value) {
                    prevItem.color = am4core.color("green");
                } else {
                    prevItem.color = am4core.color("red");
                }

                chart.addData(element);
                chart.invalidateRawData();

                let lbl = document.getElementById(label);

                if(lbl != null) {
                    lbl.innerHTML = d + u;
                }
            })
            .catch(error => console.log('Authorization failed : ' + error.message))
    }, 2000);

    element = {
        "timer": t,
        "chart": path
    }
    timer.push(element);
}
//-END-AMPERE-CHART-------------------------------------------------------------
//-CELL-CHART-------------------------------------------------------------------
function setColor(chart, series) {
    series.columns.template.adapter.add("fill", function(fill, target) {
        var i = target.dataItem.index;
        var perc = chart.data[i].voltage/* /maxVolt*100 */;

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

function getHeatData(cells, ncells, nrows, subcells, group) {
    let data = [];

    let ncols = ncells / (nrows * group);
    let nelem = nrows * subcells;

    let j = 0;
    let k = 0;
    let value = 0;

    for(let i = 0; i < cells.length; i++) {
        value += cells[i]["temp"];
        j++;

        if(j % group == 0) {
            let x = (k % subcells) + (Math.floor(k / nelem) * subcells) + 1;
            let y = Math.floor((k % nelem) / subcells) + 1;
            value = value / group;

            let element = {
                "x": x,
                "y": y,
                "color": setHeatColor(value),
                "value": value
            }

            data.push(element);

            k++;
            j = 0;
            value = 0;
        }
    }
    return data;
}

function updateHeatValue(chart, series, nrows, group) {
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

                    for(let i = k * group; i < ((k * group) + group); i++) {
                        value += cells[i]["temp"];
                    }

                    value /= group;

                    item.value = value;

                    item.color = setHeatColor(value);

                    chart.invalidateData();
                })
            })
            .catch(error => console.log('Authorization failed : ' + error.message))
    }, 2000);
}
//-END-HEAT-CHART---------------------------------------------------------------
