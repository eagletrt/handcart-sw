var href = window.location;

var page = href.pathname;

switch(page) {
    case "/":
    default:
        document.getElementById("home").classList.add("active");
        break;
    case "/settings":
        document.getElementById("settings").classList.add("active");
        break;
    case "/charts":
        let chart = href.search.split("=")[1];
        document.getElementById("side" + chart).classList.add("active");
        break;
}
