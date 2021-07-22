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
            yAxis.renderer.inversed = true;
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

            let ncells = cells.length;
            let nrows = 6;
            let ncols = ncells / nrows;
            let subcells = 3;
            let nelem = nrows * subcells;

            for(let i = 0; i < cells.length; i++) {
                let value = cells[i]["temp"];
                let x = (i % subcells) + (Math.floor(i / nelem) * subcells) + 1;
                let y = Math.floor((i % nelem) / subcells) + 1;
                let element = {
                    "x": x,
                    "y": y,
                    "color": setHeatColor(value),
                    "value": value
                }

                data.push(element);
            }

            chart.data = data;

            updateHeatValue(chart, series, nrows);

        }); // end am4core.ready()
    })
    .catch(error => console.log('Authorization failed : ' + error.message))
