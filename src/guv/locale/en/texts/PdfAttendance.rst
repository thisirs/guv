PDF file of attendance sheets

This task generates a PDF file or a zip archive of PDF files containing
attendance sheets.

{options}

Examples
--------

- Named attendance sheet:

  .. code:: bash

     guv pdf_attendance --title "Exam"

- Named attendance sheets by lab group:

  .. code:: bash

     guv pdf_attendance --title "Lab exam" --group "Lab group"

- Blank attendance sheets by lab group:

  .. code:: bash

     guv pdf_attendance --title "Lab exam" --group "Lab group" --blank

- Named attendance sheets divided across three rooms:

  .. code:: bash

     guv pdf_attendance --title "Lab exam" --count 24 24 24 --name "Room 1" "Room 2" "Room 3"
