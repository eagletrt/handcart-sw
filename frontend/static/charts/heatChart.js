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
    console.log(rgb);
    return rgb;
}

function updateHeatValue(chart, series) {
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
                    let i = parseInt((x-1)*12 + (y-1));

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

//------------------------------------------------------------------------------

var url = 'http://127.0.0.1:5000';
var path = '/bms-hv/heat';

request = getRequest(url, path);

fetch(request)
    .then(response => response.json())
    .then(json => {
        am4core.ready(function() {
            // Themes begin
            am4core.useTheme(am4themes_animated);
            // Themes end

            var chart = am4core.create("heatChart", am4charts.XYChart);
            chart.hiddenState.properties.opacity = 0; // this creates initial fade-in

            chart.maskBullets = false;

            var xAxis = chart.xAxes.push(new am4charts.CategoryAxis());
            var yAxis = chart.yAxes.push(new am4charts.CategoryAxis());

            xAxis.dataFields.category = "x";
            yAxis.dataFields.category = "y";

            xAxis.fontSize = 0;
            yAxis.fontSize = 0;

            xAxis.renderer.grid.template.disabled = true;
            xAxis.renderer.minGridDistance = 40;

            yAxis.renderer.grid.template.disabled = true;
            yAxis.renderer.inversed = false;
            yAxis.renderer.minGridDistance = 30;

            var series = chart.series.push(new am4charts.ColumnSeries());
            series.dataFields.categoryX = "x";
            series.dataFields.categoryY = "y";
            series.dataFields.value = "value";
            series.sequencedInterpolation = true;
            series.defaultState.transitionDuration = 3000;

            // Set up column appearance
            var column = series.columns.template;
            column.strokeWidth = 2;
            column.strokeOpacity = 1;
            column.stroke = am4core.color("#ffffff");
            column.tooltipText = "{value.workingValue.formatNumber('#.')}°";
            column.width = am4core.percent(100);
            column.height = am4core.percent(100);
            column.column.cornerRadius(6, 6, 6, 6);
            column.propertyFields.fill = "color";

            var data = [];
            let cells = json["data"];
            let nrows = 12;

            for(let i = 0; i < cells.length; i++) {
                let value = cells[i]["temp"];
                let element = {
                    "x": Math.floor(i / nrows) + 1,
                    "y": (i % nrows) + 1,
                    "color": setHeatColor(value),
                    "value": value
                }
                data.push(element);
            }

            chart.data = data;

            updateHeatValue(chart, series);

            /*var baseWidth = Math.min(chart.plotContainer.maxWidth, chart.plotContainer.maxHeight);
            var maxRadius = baseWidth / Math.sqrt(chart.data.length) / 2 - 2; // 2 is jast a margin
            series.heatRules.push({ min: 10, max: maxRadius, property: "radius", target: bullet1.circle });*/
        }); // end am4core.ready()
    })
    .catch(error => console.log('Authorization failed : ' + error.message))
