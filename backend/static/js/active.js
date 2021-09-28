var href = window.location;

var page = href.pathname.substring(1); // to remove the "/" before the page's name

switch(page) {
    case "":
    default:
        document.getElementById("home").classList.add("active");
        break;
    case "settings":
        document.getElementById("settings").classList.add("active");
        break;
    case "charts":
        let chart = href.search.split("=")[1];
        document.getElementById("side" + chart).classList.add("active");
        break;
    case "warnings":
    case "errors":
        break;
}
