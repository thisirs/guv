// ==UserScript==
// @name Moodle download groups
// @version  1
// @include https://moodle.utc.fr/user/index.php*
// @run-at      document-idle
// ==/UserScript==

var zNode = document.createElement('div');
zNode.innerHTML = '<button id="myButton" type="button">Download group</button>';

zNode.setAttribute('id', 'myContainer');
document.getElementsByClassName("btn-group")[0].appendChild(zNode);

//--- Activate the newly added button.
document.getElementById("myButton").addEventListener(
    "click", ButtonClickAction, false
);

function ButtonClickAction (zEvent) {
    var separator = ',';
    var csv = [['email','group'].join(separator)];
    trs = document.querySelectorAll('table[id=participants]>tbody>tr[class=""]');

    for (i = 0; i < trs.length; i++) {
        tr = trs[i]
        tds = tr.getElementsByTagName('td');
        name = tds[0].innerText;
        email = tds[1].innerText;
        groups = tds[3].innerText.trim().split(/,* /);

        for (j = 0; j < groups.length; j++) {
            var r = [];
            // r.push(name);
            r.push(email);
            r.push(groups[j]);

            csv.push(r.join(separator));
        }
    }
    csv = csv.join("\r\n");
    window.open("data:text/csv;charset=utf-8," + encodeURIComponent(csv));
}
