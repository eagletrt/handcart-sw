function createChargeChart() {
    am4core.ready(function () {

        // Themes begin
        am4core.useTheme(am4themes_animated);
        // Themes end

        // create chart
        var chart = am4core.create("chargeChart", am4charts.GaugeChart);
        chart.innerRadius = am4core.percent(70);
        chart.startAngle = 130;
        chart.endAngle = 410;

        /**
         * Normal axis
         */

        var axis = chart.xAxes.push(new am4charts.ValueAxis());
        axis.min = 0;
        axis.max = 100;
        axis.strictMinMax = false;
        axis.renderer.radius = am4core.percent(0);

        /**
         * Axis for ranges
         */

        var axis2 = chart.xAxes.push(new am4charts.ValueAxis());
        axis2.min = 0;
        axis2.max = 100;
        axis2.strictMinMax = true;
        axis2.renderer.labels.template.disabled = true;
        axis2.renderer.ticks.template.disabled = true;
        axis2.renderer.grid.template.disabled = true;

        var range0 = axis2.axisRanges.create();
        range0.value = 0;
        range0.endValue = 0;
        range0.axisFill.fillOpacity = 1;
        range0.axisFill.fill = am4core.color("green");

        var range1 = axis2.axisRanges.create();
        range1.value = 0;
        range1.endValue = 100;
        range1.axisFill.fillOpacity = 1;
        range1.axisFill.fill = am4core.color("red");

        /**
         * Label
         */

        var label = chart.radarContainer.createChild(am4core.Label);
        label.isMeasured = false;
        label.fontSize = 45;
        label.x = am4core.percent(0);
        label.y = am4core.percent(100);
        label.horizontalCenter = "middle";
        label.verticalCenter = "middle";
        label.text = "0%";


        /**
         * Hand
         */

        var hand = chart.hands.push(new am4charts.ClockHand());
        hand.axis = axis2;
        hand.value = 0;
        hand.visible = false;

        hand.events.on("propertychanged", function (ev) {
            range0.endValue = ev.target.value;
            range1.value = ev.target.value;
            label.text = axis2.positionToValue(hand.currentPosition).toFixed(1) + "%";
            axis2.invalidate();
        });

        setInterval(function () {
            let volt = parseInt(document.getElementById("volt").innerHTML); // insert the value in the top bar
            let minCOVolt = 330;
            let coVolt = parseInt(document.getElementById("COvolt").innerHTML);

            let value = Math.max(0, Math.round((100 * (volt-minCOVolt) / (coVolt-minCOVolt))));

            document.getElementById("charge").innerHTML = Math.round(value) + "%"; // calculate the value of the charge

            //var value = Math.round(Math.random() * 100);
            var animation = new am4core.Animation(hand, {
                property: "value",
                to: value
            }, 1000, am4core.ease.cubicOut).start();
        }, 2000);

    }); // end am4core.ready()
}
