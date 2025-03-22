// ==UserScript==
// @name     Set datetime from clipboard
// @version  1
// @grant    none
// @include https://moodle.utc.fr/course/modedit.php*
// @run-at      document-idle
// ==/UserScript==

(function() {
    'use strict';

    function createButton() {
        let parentContainer = document.querySelector("#id_timingcontainer");
        if (!parentContainer) return;

        parentContainer.insertAdjacentHTML('beforeend', `
<div id="fitem_id_parsebutton" class="form-group row  fitem femptylabel  ">
  <div class="col-md-3 col-form-label d-flex pb-0 pr-md-0">
    <div class="form-label-addon d-flex align-items-center align-self-start">
    </div>
  </div>
  <div class="col-md-9 form-inline align-items-start felement" data-fieldtype="static">
    <div class="form-control-static">
      <button id="parsejson" type="button" class="btn btn-secondary" data-groupavailability="1" data-groupingavailability="1">Parse JSON</button>
    </div>
    <div class="form-control-feedback invalid-feedback" id="id_error_parsegroupbutton">
    </div>
  </div>
</div>
            `);

        // Select the newly created button
        let button = document.querySelector('#parsejson');

        if (button) {
            // Add event listener to the button
            button.addEventListener('click', pasteJson);
        }

    }

    function pasteJson() {
        let jsonInput = prompt("Paste your JSON:");
        if (!jsonInput) return;

        try {
            let data = JSON.parse(jsonInput);
            if (!data.start && !data.end) {
                alert("Invalid JSON: Missing start or end timestamps");
                return;
            }

            populateFields(data.start, data.end);
        } catch (e) {
            alert("Invalid JSON format");
        }
    }

    function populateFields(startTimestamp, endTimestamp) {
        function setValue(selector, value) {
            let select = document.querySelector(selector);
            if (select) {
                select.value = value;
            }
        }

        if (startTimestamp) {
            let startDate = new Date(startTimestamp * 1000);
            setValue("#id_timeopen_day", startDate.getDate());
            setValue("#id_timeopen_month", startDate.getMonth() + 1); // Months are 0-based
            setValue("#id_timeopen_year", startDate.getFullYear());
            setValue("#id_timeopen_hour", startDate.getHours());
            setValue("#id_timeopen_minute", startDate.getMinutes());
        }
        let startCheckbox = document.querySelector("#id_timeopen_enabled");
        startCheckbox.checked = typeof startTimestamp !== 'undefined';
        let startEvent = new Event('change', { bubbles: true });
        startCheckbox.dispatchEvent(startEvent);


        if (endTimestamp) {
            let endDate = new Date(endTimestamp * 1000);
            setValue("#id_timeclose_day", endDate.getDate());
            setValue("#id_timeclose_month", endDate.getMonth() + 1); // Months are 0-based
            setValue("#id_timeclose_year", endDate.getFullYear());
            setValue("#id_timeclose_hour", endDate.getHours());
            setValue("#id_timeclose_minute", endDate.getMinutes());
        }
        let endCheckbox = document.querySelector("#id_timeclose_enabled");
        endCheckbox.checked = typeof endTimestamp !== 'undefined';
        let endEvent = new Event('change', { bubbles: true });
        endCheckbox.dispatchEvent(endEvent);
    }

    createButton();
})();
