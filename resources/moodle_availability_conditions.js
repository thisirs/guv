// ==UserScript==
// @name     Show hidden json textarea in Moodle
// @version  1
// @grant    none
// @include https://moodle.utc.fr/course/modedit.php*
// @include https://moodle.utc.fr/course/editsection.php*
// @run-at      document-idle
// ==/UserScript==

elt = document.getElementById('id_availabilityconditionsjson');
elt.setAttribute("aria-hidden", "false");

var i = setInterval(function() {
    elt = document.getElementById('id_availabilityconditionsjson');
    elt.setAttribute("aria-hidden", "false");
}, 1000);
