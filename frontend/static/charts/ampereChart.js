function updateAmpereValue(chart, series) {
    setInterval(function () {
        var url = 'http://127.0.0.1:5000';
        var path = '/bms-hv/ampere/last';

        request = getRequest(url, path);

        fetch(request)
            .then(response => response.json())
            .then(json => {
                timestamp = json[0]["timestamp"]
                volt = json[0]["amperes"]
                element = {
                    date: new Date(timestamp),
                    value: volt
                }
                chart.addData(element, 1);
            })
            .catch(error => console.log('Authorization failed : ' + error.message))
    }
    , 2000);
}

var url = 'http://127.0.0.1:5000';
var path = '/bms-hv/ampere';

request = getRequest(url, path);

fetch(request)
    .then(response => response.json())
    .then(json => {
        am4core.ready(function() {

            // Themes begin
            am4core.useTheme(am4themes_animated);
            // Themes end

            var chart = am4core.create("ampereChart", am4charts.XYChart);
            //chart.paddingRight = 20;

            chart.zoomOutButton.disabled = true;

            var data = [];
            var volt = 10;
            var previousValue;
            amperes = json[0]["data"];
            n = amperes.length;

            for (var i = 0; i < n; i++) {
                amp = amperes[i]["amperes"];

                if (i > 0) {
                    // add color to previous data item depending on whether current value is less or more than previous value
                    if (previousValue <= amp) {
                        data[i - 1].color = am4core.color("green");
                    } else {
                        data[i - 1].color = am4core.color("red");
                    }
                }

                element = {
                    date: new Date(voltages[i]["timestamp"]),
                    value: amp
                };

                data.push(element);
                previousValue = amp;
            }

            chart.data = data;

            var dateAxis = chart.xAxes.push(new am4charts.DateAxis());
            dateAxis.renderer.grid.template.location = 0;
            dateAxis.renderer.minGridDistance = 30;
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
                dateAxis.zoom({ start: 1/1.25, end: 1.1 }, false, true);
            });

            var valueAxis = chart.yAxes.push(new am4charts.ValueAxis());
            valueAxis.tooltip.disabled = true;
            valueAxis.renderer.minWidth = 35;
            //*
            valueAxis.interpolationDuration = 500;
            valueAxis.rangeChangeDuration = 500;
            //valueAxis.renderer.inside = true;
            valueAxis.renderer.minLabelPosition = 0.05;
            valueAxis.renderer.maxLabelPosition = 0.95;
            //*
            valueAxis.renderer.axisFills.template.disabled = true;
            valueAxis.renderer.ticks.template.disabled = true;

            var series = chart.series.push(new am4charts.LineSeries());
            series.dataFields.dateX = "date";
            series.dataFields.valueY = "value";
            series.strokeWidth = 2;
            series.fillOpacity = 0.25;
            series.fill = am4core.color("green");
            series.tooltipText = "Amperes: {valueY}\nChange: {valueY.previousChange}";
            series.tooltip.getFillFromObject = false;
            series.tooltip.background.fill = "rgba(255, 0, 0, 0.5)";
            //*
            series.interpolationDuration = 500;
            series.defaultState.transitionDuration = 0;
            //series.tensionX = 0.8;

            dateAxis.interpolationDuration = 500;
            dateAxis.rangeChangeDuration = 500;
            //*

            // set stroke property field
            series.propertyFields.stroke = "color";
            //series.propertyFields.fill = "color";

            chart.cursor = new am4charts.XYCursor();

            /*var scrollbarX = new am4core.Scrollbar();
            chart.scrollbarX = scrollbarX;*/

            dateAxis.start = 0;
            dateAxis.keepSelection = true;

            updateAmpereValue(chart, series);

            //******************************************************************

            // this makes date axis labels which are at equal minutes to be rotated
            dateAxis.renderer.labels.template.adapter.add("rotation", function (rotation, target) {
                var dataItem = target.dataItem;
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

            // this makes date axis labels to fade out
            dateAxis.renderer.labels.template.adapter.add("fillOpacity", function (fillOpacity, target) {
                var dataItem = target.dataItem;
                return dataItem.position;
            })

            // need to set this, otherwise fillOpacity is not changed and not set
            dateAxis.events.on("validated", function () {
                am4core.iter.each(dateAxis.renderer.labels.iterator(), function (label) {
                    label.fillOpacity = label.fillOpacity;
                })
            })

            // bullet at the front of the line
            var bullet = series.createChild(am4charts.CircleBullet);
            bullet.circle.radius = 3;
            bullet.fillOpacity = 1;
            bullet.fill = am4core.color("green");
            bullet.stroke = am4core.color("green");
            bullet.isMeasured = false;

            series.events.on("validated", function() {
              bullet.moveTo(series.dataItems.last.point);
              bullet.validatePosition();
            });
        }); // end am4core.ready()
    })
    .catch(error => console.log('Authorization failed : ' + error.message))