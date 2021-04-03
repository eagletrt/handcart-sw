// Add data
/*chart.data = [];
ncells = 100;

for (i = 0; i < ncells; i++) {
    voltage = Math.floor(Math.random() * 101);
    cellName = "CELL " + (i + 1);

    element = {
        "cell": cellName,
        "voltage": voltage
    };
    chart.data.push(element);
}*/

function setColor(chart, series) {
    series.columns.template.adapter.add("fill", function(fill, target) {
        var i = target.dataItem.index;
        var perc = chart.data[i].voltage;

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
                    i = parseInt(item["cell"].substr(5)) - 1
                    cells = json[0]["cells"]
                    voltage = cells[i]["voltage"]

                    item.voltage = voltage
                })
                chart.invalidateData()
            })
            .catch(error => console.log('Authorization failed : ' + error.message))
    }
    , 2000);
}

//------------------------------------------------------------------------------

var url = 'http://127.0.0.1:5000';
var path = '/bms-hv/cells';

request = getRequest(url, path);

fetch(request)
    .then(response => response.json())
    .then(json => {
        am4core.ready(function() {

            // Themes begin
            am4core.useTheme(am4themes_animated);
            // Themes end

            // Create chart instance
            var chart = am4core.create("cellChart", am4charts.XYChart);
            chart.scrollbarX = new am4core.Scrollbar();

            chart.data = [];
            cells = json[0]["data"][0]["cells"];
            ncells = cells.length;

            for (i = 0; i < ncells; i++) {
                voltage = cells[i]["voltage"];
                cellName = "CELL " + (i + 1);

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
            categoryAxis.renderer.minHeight = 110;

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

        }); // end am4core.ready()
    })
    .catch(error => console.log('Authorization failed : ' + error.message))