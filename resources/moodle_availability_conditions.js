// ==UserScript==
// @name     Show hidden json textarea in Moodle
// @version  1
// @grant    none
// @include https://moodle.utc.fr/course/modedit.php*
// @include https://moodle.utc.fr/course/editsection.php*
// @run-at      document-idle
// ==/UserScript==

let elt = document.querySelector("#id_availabilityconditionsjson");
let observer = new MutationObserver(function(mutations, obs) {
    mutations.forEach(function(mutation) {
        if (mutation.type === 'attributes' && mutation.attributeName === "aria-hidden") {
            obs.disconnect();
            elt.setAttribute("aria-hidden", "false");
            obs.observe(elt, {attributes: true});
        }
    });
});

observer.observe(elt, {
    attributes: true
});

