am4core.ready(function() {

    // Themes begin
    am4core.useTheme(am4themes_animated);
    // Themes end

    var chart = am4core.create("voltChart", am4charts.XYChart);
    chart.paddingRight = 20;

    var data = [];
    var visits = 10;
    var previousValue;

    for (var i = 0; i < 100; i++) {
        visits += Math.round((Math.random() < 0.5 ? 1 : -1) * Math.random() * 10);

        if (i > 0) {
            // add color to previous data item depending on whether current value is less or more than previous value
            if (previousValue <= visits) {
                data[i - 1].color = am4core.color("green");
            } else {
                data[i - 1].color = am4core.color("red");
            }
        }

        data.push({
            date: new Date(2018, 0, i + 1),
            value: visits
        });
        previousValue = visits;
    }

    chart.data = data;

    var dateAxis = chart.xAxes.push(new am4charts.DateAxis());
    dateAxis.renderer.grid.template.location = 0;
    dateAxis.renderer.axisFills.template.disabled = true;
    dateAxis.renderer.ticks.template.disabled = true;

    var valueAxis = chart.yAxes.push(new am4charts.ValueAxis());
    valueAxis.tooltip.disabled = true;
    valueAxis.renderer.minWidth = 35;
    valueAxis.renderer.axisFills.template.disabled = true;
    valueAxis.renderer.ticks.template.disabled = true;

    var series = chart.series.push(new am4charts.LineSeries());
    series.dataFields.dateX = "date";
    series.dataFields.valueY = "value";
    series.strokeWidth = 2;
    series.fillOpacity = 0.25;
    series.fill = am4core.color("green");
    series.tooltipText = "Battery: {valueY}\nChange: {valueY.previousChange}";
    series.tooltip.getFillFromObject = false;
    series.tooltip.background.fill = "rgba(255, 0, 0, 0.5)";

    // set stroke property field
    series.propertyFields.stroke = "color";
    //series.propertyFields.fill = "color";

    chart.cursor = new am4charts.XYCursor();

    var scrollbarX = new am4core.Scrollbar();
    chart.scrollbarX = scrollbarX;

    dateAxis.start = 0;
    dateAxis.keepSelection = true;


}); // end am4core.ready()
