Zip file of personalized attendance sheets by group and semester

Generates a zip file containing one attendance sheet per group for the entire
semester. This makes it possible to have a single document for attendance
tracking over the semester.

{options}

Examples
--------

.. code:: bash

   guv pdf_attendance_full -n 7
   guv pdf_attendance_full --group "Lab work" --template "Session {{number}}"
