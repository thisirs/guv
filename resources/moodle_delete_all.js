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
removeAllBtn.setAttribute("value", "Supprimer tout ►")
removeAllBtn.disabled = false

removeAllBtn.onclick = function() {
    let sel = document.getElementById("removeselect")
    for (var i=0; i<sel.options.length; i++) {
        sel.options[i].selected = true;
    }
};


lineBreak = document.createElement('br')
removeSelectBtn.after(lineBreak, removeAllBtn)
