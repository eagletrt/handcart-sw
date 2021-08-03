function createCellChart() {
    //var url = 'http://127.0.0.1:5000';
    var path = '/bms-hv/cells/last';

    request = getRequest(url, path);

    fetch(request)
        .then(response => response.json())
        .then(json => {
            am4core.ready(function () {

                // Themes begin
                am4core.useTheme(am4themes_animated);
                // Themes end

                // Create chart instance
                var chart = am4core.create("cellChart", am4charts.XYChart);
                chart.scrollbarX = new am4core.Scrollbar();

                chart.data = [];
                let cells = json["cells"];
                let ncells = cells.length;

                for (i = 0; i < ncells; i++) {
                    voltage = cells[i]["voltage"];
                    cellName = (i + 1);

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

                setColor(chart, series);

                // Cursor
                chart.cursor = new am4charts.XYCursor();

                updateCellValue(chart, series);

                // check if it has been called from the home page
                // if not, than set an event listener to check every single cell
                let href = window.location.href;
                let re = /.*\/(.*)/;
                let page = href.match(re)[1];

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
