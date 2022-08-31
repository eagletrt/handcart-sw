function createCellChart() {
    var path = 'bms-hv/cells/voltage/last';

    let min = 2.8;
    let max = 4.3;

    request = getRequest(url, path);

    fetch(request)
        .then(response => {
            if(!response.ok) {
                document.getElementById("cellChart").innerHTML = errMsg;
                throw new Error("Error code " + response.status + ": " + errMsg);
            }
            return response.json();
        })
        .then(json => {
            am4core.ready(function () {

                // Themes begin
                am4core.useTheme(am4themes_animated);
                // Themes end

                // Create chart instance
                var chart = am4core.create("cellChart", am4charts.XYChart);
                chart.scrollbarX = new am4core.Scrollbar();

                chart.data = [];
                console.log("Cell charge: ")
                console.log(json)
                let cells = json["cells"];
                let ncells = cells.length;

                for (i = 0; i < ncells; i++) {
                    voltage = cells[i]["voltage"];
                    cellName = i;

                    element = {
                        "cell": cellName,
                        "voltage": voltage
                    }
                    chart.addData(element);
                }

                // Create axes
                var categoryAxis = chart.xAxes.push(new am4charts.CategoryAxis());
                categoryAxis.dataFields.category = "cell";
                categoryAxis.renderer.grid.template.location = 0;
                categoryAxis.renderer.minGridDistance = 30;
                categoryAxis.renderer.labels.template.horizontalCenter = "right";
                categoryAxis.renderer.labels.template.verticalCenter = "middle";
                categoryAxis.renderer.labels.template.rotation = 270;
                categoryAxis.renderer.minHeight = 10;

                var valueAxis = chart.yAxes.push(new am4charts.ValueAxis());
                valueAxis.renderer.minWidth = 50;
                valueAxis.tooltip.disabled = true;

                valueAxis.min = min;
                valueAxis.max = max;

                // Create series
                var series = chart.series.push(new am4charts.ColumnSeries());
                series.sequencedInterpolation = true;
                series.dataFields.valueY = "voltage";
                series.dataFields.categoryX = "cell";
                series.tooltipText = "[{categoryX}: bold]{valueY}[/]";
                series.columns.template.strokeWidth = 0;

                series.tooltip.pointerOrientation = "vertical";

                series.columns.template.column.cornerRadiusTopLeft = 10;
                series.columns.template.column.cornerRadiusTopRight = 10;
                series.columns.template.column.fillOpacity = 0.8;

                // on hover, make corner radiuses bigger
                var hoverState = series.columns.template.column.states.create("hover");
                hoverState.properties.cornerRadiusTopLeft = 0;
                hoverState.properties.cornerRadiusTopRight = 0;
                hoverState.properties.fillOpacity = 1;

                setColor(chart, series, max);

                // Cursor
                chart.cursor = new am4charts.XYCursor();

                updateCellValue(chart, series);

                // check if it has been called from the home page
                // if not, than set an event listener to check every single cell
                let href = window.location;

                let page = href.pathname.substring(1); // to remove the "/" before the page's name

                if (page != "") {
                    series.columns.template.events.on("hit", function (ev) {
                        let index = parseInt(ev.target.dataItem.index) + 1;
                        getCell(index);
                    }, this);
                }

            }); // end am4core.ready()
        })
        .catch(error => console.log('Authorization failed : ' + error.message))
}
