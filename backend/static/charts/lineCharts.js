async function createLineChart(basicPath, name, param, zoom, label, u) {
    let NZ = "nozoom";

    am4core.ready(async function () {

        // Themes begin
        am4core.useTheme(am4themes_animated);
        // Themes end

        var chart = am4core.create(name + "Chart", am4charts.XYChart);
        //chart.paddingRight = 20;

        var exit = false;
        var from = 0;
        var step = 100;

        var data = [];
        var previousValue = -1;

        var x = 0;

        while(!exit) {
            path = basicPath + "?from=" + from + "&to=" + (from + step);
            //console.log(url + path)
            request = getRequest(url, path);

            x++;
            //console.log("request number " + x + ": from " + from + " to " + (from+step));
            
            await fetch(request)
                .then(response => {
                    if(!response.ok) {
                        exit = true;
                        document.getElementById(name + "Chart").innerHTML = errMsg;
                        throw new Error("Error code " + response.status + ": " + errMsg + " (BMS-HV)");
                    }
                    return response.json();
                })
                .then(json => {
                    let jdata = json["data"];
                    let n = jdata.length;

                    if(zoom == NZ) {
                        for(let i = 0; i < n; i++) {
                            let d = jdata[i][param];
                            let timestamp = new Date(jdata[i]["timestamp"]);

                            if(i > 0) {
                                // add color to previous data item depending on whether current value is less or more than previous value
                                if(previousValue <= d) {
                                    data[i - 1].color = am4core.color("green");
                                } else {
                                    data[i - 1].color = am4core.color("red");
                                }
                            }

                            let element = {
                                date: timestamp,
                                value: d
                            };

                            data.push(element);
                            previousValue = d;
                        }
                    }

                    if(json["remaining"] == 0 || zoom != NZ) {
                        exit = true;
                    } else {
                        from += step;
                    }

                    if(data.length == 0) {
                        for(let i = 0; i <= 10; i++) {
                            let element = {
                                date: new Date().setSeconds(i - 30),
                                value: 0
                            }
                            element.color = am4core.color("green");

                            data.push(element);
                        }
                    }
                })
                .catch(error => console.log('Authorization failed : ' + error.message))
        }

        chart.data = data;

        let nameChart = name[0].toUpperCase() + name.substring(1);

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

        var valueAxis = chart.yAxes.push(new am4charts.ValueAxis());
        valueAxis.tooltip.disabled = true;
        valueAxis.renderer.minWidth = 35;
        valueAxis.title.text = nameChart + " (" + u + ")";

        //*
        valueAxis.interpolationDuration = 500;
        valueAxis.rangeChangeDuration = 500;
        //valueAxis.renderer.inside = true;
        valueAxis.renderer.minLabelPosition = 0.05;
        valueAxis.renderer.maxLabelPosition = 0.95;
        //*
        valueAxis.renderer.axisFills.template.disabled = true;
        valueAxis.renderer.ticks.template.disabled = true;

        valueAxis.min = 0;

        //------------------------------------------------------------------------------------------------------
        var series = chart.series.push(new am4charts.LineSeries());
        series.dataFields.dateX = "date";
        series.dataFields.valueY = "value";
        series.strokeWidth = 2;
        series.fillOpacity = 0.25;
        series.fill = am4core.color("green");
        series.tooltipText = nameChart + ": {valueY}\nChange: {valueY.previousChange}";
        series.tooltip.getFillFromObject = false;
        series.tooltip.background.fill = "rgba(255, 0, 0, 0.5)";
        //*
        series.interpolationDuration = 500;
        series.defaultState.transitionDuration = 0;
        //series.tensionX = 0.8;
        //------------------------------------------------------------------------------------------------------

        dateAxis.interpolationDuration = 500;
        dateAxis.rangeChangeDuration = 500;
        //*

        // set stroke property field
        series.propertyFields.stroke = "color";
        //series.propertyFields.fill = "color";

        chart.cursor = new am4charts.XYCursor();

        dateAxis.start = 0;
        dateAxis.keepSelection = true;

        let lastPath = basicPath + "/last";  // must be called to update headers values
        if(zoom != NZ) {
            chart.zoomOutButton.disabled = true;

            if (basicPath.includes("?")) { // check if there are parameters
                let matches = path.match(/(.*)(\?.*)/); // create a new string to ask latest data
                lastPath = matches[1] + "/last" + matches[2];
            }

            // bullet at the front of the line
            var bullet = series.createChild(am4charts.CircleBullet);
            bullet.circle.radius = 3;
            bullet.fillOpacity = 1;
            bullet.fill = am4core.color("green");
            bullet.stroke = am4core.color("green");
            bullet.isMeasured = false;

            series.events.on("validated", function () {
                bullet.moveTo(series.dataItems.last.point);
                bullet.validatePosition();
            });

            // this makes date axis labels to fade out
            dateAxis.renderer.labels.template.adapter.add("fillOpacity", function (fillOpacity, target) {
                var dataItem = target.dataItem;
                return dataItem.position;
            })
        } else {

            /*var scrollbarX = new am4core.Scrollbar();
            chart.scrollbarX = scrollbarX;*/
        }

        updateLineChartValue(chart, lastPath, param, zoom, label);

        //**************************************************************

        // this makes date axis labels which are at equal minutes to be rotated
        dateAxis.renderer.labels.template.adapter.add("rotation", function (rotation, target) {
            let dataItem = target.dataItem;
            if (dataItem.date && dataItem.date.getTime() == am4core.time.round(new Date(dataItem.date.getTime()), "minute").getTime()) {
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
}
