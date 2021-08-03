var href = window.location.href;

var re = /.*\/(.*)/; // output anything after the last "/" in actual the URL

var page = href.match(re)[1]; // return the page name, without the whole link before

switch (page) {
    case "":
        document.getElementById("home").classList.add("active");
        break;
    case "settings":
        document.getElementById("settings").classList.add("active");
        break;
}
