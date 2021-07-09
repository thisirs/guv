// ==UserScript==
// @name Moodle download groupings
// @version  1
// @include https://moodle.utc.fr/group/groupings.php*
// @run-at      document-idle
// ==/UserScript==

var zNode = document.createElement('div');
zNode.innerHTML = '<button id="myButton" class="btn btn-secondary", "type="button">Download groupings</button>';
zNode.setAttribute('id', 'myContainer');

document.getElementsByClassName("buttons")[0].appendChild(zNode);

document.getElementById("myButton").addEventListener(
    "click", ButtonClickAction, false
);

function ButtonClickAction (zEvent) {
    var separator = ',';
    var csv = [['grouping','group'].join(separator)];
    trs = document.querySelectorAll('table[class=generaltable]>tbody>tr');

    for (i = 0; i < trs.length; i++) {
        tr = trs[i]
        tds = tr.getElementsByTagName('td');
        name = tds[0].innerText;
        groups = tds[1].innerText.trim().split(/, /);

        for (j = 0; j < groups.length; j++) {
            var r = [];
            // r.push(name);
            r.push(name);
            r.push(groups[j]);
            csv.push(r.join(separator));
        }
    }
    csv = csv.join("\r\n");
    window.open("data:text/csv;charset=utf-8," + encodeURIComponent(csv));
}
