function createMultilineChart(path, name, param, zoom, label, u) {
    let NZ = "nozoom";

    request = getRequest(url, path);

    fetch(request)
        .then(response => {
            if(!response.ok) {
                document.getElementById(name + "Chart").innerHTML = errMsg;
                throw new Error("Error code " + response.status + ": " + errMsg + " (BMS-HV)");
            }
            return response.json();
        })
        .then(json => {
            am4core.ready(function () {
                // Themes begin
                am4core.useTheme(am4themes_animated);
                var colorSet = new am4core.ColorSet();
                // Themes end

                var chart = am4core.create(name + "Chart", am4charts.XYChart);
                //chart.paddingRight = 20;
                console.log(json)
                let data = [];
                let keys = [];
                let previousValue = -1;

                let jdata = json["data"];
                let n = jdata.length;

                if(zoom == NZ) {
                    for(let i = 0; i < n; i++) {
                        let element = {};
                        for(let key in jdata[i]) {
                            let d = jdata[i][key];
                            if(key != "timestamp") {
                                if(i == 0) {
                                    keys.push(key);
                                } else if(key == param) {
                                    if (previousValue <= d) {
                                        data[i - 1].color = am4core.color("green");
                                    } else {
                                        data[i - 1].color = am4core.color("red");
                                    }
                                    previousValue = d;
                                }
                                element[key] = d;
                            } else {
                                element["date"] = new Date(d);
                            }
                        }
                        data.push(element);
                    }
                }

                if(data.length == 0) {
                    for (let i = 0; i <= 30; i++) {
                        let element = {};
                        for(let key in jdata[i]) {
                            let d = jdata[i][key];
                            if(key != "timestamp") {
                                if(i == 0) {
                                    keys.push(key);
                                } else if(key == param) {
                                    element.color = am4core.color("green");
                                }
                                element[key] = 0;
                            } else {
                                element["date"] = new Date().setSeconds(i - 30);
                            }
                        }

                        data.push(element);
                    }
                }

                chart.data = data;

                var dateAxis = chart.xAxes.push(new am4charts.DateAxis());
                dateAxis.renderer.grid.template.location = 0;
                dateAxis.renderer.minGridDistance = 30;
                dateAxis.tooltip.disabled = true;
                //*
                dateAxis.dateFormats.setKey("second", "ss");
                dateAxis.periodChangeDateFormats.setKey("second", "[bold]h:mm a");
                dateAxis.periodChangeDateFormats.setKey("minute", "[bold]h:mm a");
                dateAxis.periodChangeDateFormats.setKey("hour", "[bold]h:mm a");
                dateAxis.renderer.inside = true;
                //*
                dateAxis.renderer.axisFills.template.disabled = true;
                dateAxis.renderer.ticks.template.disabled = true;

                chart.events.on("datavalidated", function () {
                    dateAxis.zoom({start: 1 / zoom, end: 1.1}, false, true);
                });

                for(let key in keys) {
                    let k = keys[key];

                    let valueAxis = chart.yAxes.push(new am4charts.ValueAxis());
                    valueAxis.tooltip.disabled = true;
                    valueAxis.renderer.minWidth = 35;
                    //*
                    valueAxis.interpolationDuration = 500;
                    valueAxis.rangeChangeDuration = 500;

                    valueAxis.renderer.minLabelPosition = 0.05;
                    valueAxis.renderer.maxLabelPosition = 0.95;
                    //*
                    valueAxis.renderer.axisFills.template.disabled = true;
                    valueAxis.renderer.ticks.template.disabled = true;

                    let nameChart = name[0].toUpperCase() + name.substring(1);

                    let series = chart.series.push(new am4charts.LineSeries());
                    series.stacked = true;
                    series.yAxis = valueAxis;
                    series.name = k;
                    series.dataFields.dateX = "date";
                    series.dataFields.valueY = k;
                    series.strokeWidth = 2;
                    series.fillOpacity = 0.25;
                    let tooltipName = k.split("_");
                    let str = ""
                    for(let i in tooltipName) {
                        str += tooltipName[i] + " ";
                    }
                    series.tooltipText = str[0].toUpperCase() + str.substring(1) + ": {valueY}\nChange: {valueY.previousChange}";
                    series.tooltip.getFillFromObject = false;
                    series.tooltip.background.fill = "rgba(255, 0, 0, 0.5)";
                    series.interpolationDuration = 500;
                    series.defaultState.transitionDuration = 0;
                    if(k == param) {
                        series.propertyFields.stroke = "color";
                    } else {
                        valueAxis.renderer.opposite = true;
                        valueAxis.renderer.inside = true;
                        let actualColor = colorSet.next();
                        valueAxis.renderer.labels.template.fill = actualColor;
                        series.propertyFields.stroke = actualColor;
                    }

                    let lastPath = path + "/last";  // must be called to update headers values
                    if(zoom != NZ) {
                        if(path.includes("?")) {       // check if there are parameters
                            let matches = path.match(/(.*)(\?.*)/); // create a new string to ask latest data
                            lastPath = matches[1] + "/last" + matches[2];
                        }

                        if(keys[key] == param) {
                            valueAxis.title.text = nameChart + " (" + u + ")";
                        }

                        chart.zoomOutButton.disabled = true;

                        updateMultilineChartValue(chart, series, lastPath, param, zoom, label);

                        // bullet at the front of the line
                        let bullet = series.createChild(am4charts.CircleBullet);
                        bullet.circle.radius = 3;
                        bullet.fillOpacity = 1;
                        bullet.fill = am4core.color("green");
                        bullet.stroke = am4core.color("green");
                        bullet.isMeasured = false;

                        series.events.on("validated", function () {
                            bullet.moveTo(series.dataItems.last.point);
                            bullet.validatePosition();
                        });
                    }
                }

                dateAxis.interpolationDuration = 500;
                dateAxis.rangeChangeDuration = 500;
                //*

                chart.cursor = new am4charts.XYCursor();

                dateAxis.start = 0;
                dateAxis.keepSelection = true;

                if(zoom != NZ) {

                    // this makes date axis labels to fade out
                    dateAxis.renderer.labels.template.adapter.add("fillOpacity", function (fillOpacity, target) {
                        var dataItem = target.dataItem;
                        return dataItem.position;
                    })
                } else {
                    chart.legend = new am4charts.Legend();
                    chart.legend.useDefaultMarker = true;
                    var marker = chart.legend.markers.template.children.getIndex(0);
                    marker.strokeWidth = 2;
                    marker.strokeOpacity = 1;

                    /*
                    var scrollbarX = new am4core.Scrollbar();
                    chart.scrollbarX = scrollbarX;
                    */
                }

                //**************************************************************

                // this makes date axis labels which are at equal minutes to be rotated
                dateAxis.renderer.labels.template.adapter.add("rotation", function (rotation, target) {
                    let dataItem = target.dataItem;
                    if(dataItem.date && dataItem.date.getTime() == am4core.time.round(new Date(dataItem.date.getTime()), "minute").getTime()) {
                        target.verticalCenter = "middle";
                        target.horizontalCenter = "left";
                        return -90;
                    } else {
                        target.verticalCenter = "bottom";
                        target.horizontalCenter = "middle";
                        return 0;
                    }
                })

                // need to set this, otherwise fillOpacity is not changed and not set
                dateAxis.events.on("validated", function () {
                    am4core.iter.each(dateAxis.renderer.labels.iterator(), function (label) {
                        label.fillOpacity = label.fillOpacity;
                    })
                })
            }); // end am4core.ready()
        })
        .catch(error => console.log('Authorization failed : ' + error.message))
}
