// ==UserScript==
// @name Moodle delete all members
// @version  1
// @include https://moodle.utc.fr/group/members.php?group=*
// @run-at      document-idle
// ==/UserScript==

// Clone remove button
removeSelectBtn = document.getElementById("remove")
removeAllBtn = removeSelectBtn.cloneNode(true)
removeAllBtn.setAttribute('id', "removeall");
removeAllBtn.disabled = false

removeAllBtn.onclick = function() {
    sel = document.getElementById("removeselect")
    for (var i=0; i<sel.options.length; i++) {
        sel.options[i].selected = true;
    }
};


// Add button after
lineBreak = document.createElement('br')
document.getElementsByClassName("arrow_button")[0].appendChild(lineBreak)
document.getElementsByClassName("arrow_button")[0].appendChild(removeAllBtn)
