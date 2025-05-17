PDF file of attendance sheets

This task generates a PDF file or a zip archive of PDF files containing
attendance sheets.

{options}

Examples
--------

- Named attendance sheet:

  .. code:: bash

     guv pdf_attendance --title "Exam"

- Named attendance sheets by TP group:

  .. code:: bash

     guv pdf_attendance --title "Examen de TP" --group TP

- Blank attendance sheets by TP group:

  .. code:: bash

     guv pdf_attendance --title "Examen de TP" --group TP --blank

- Named attendance sheets divided across three rooms:

  .. code:: bash

     guv pdf_attendance --title "Examen de TP" --count 24 24 24 --name "Salle 1" "Salle 2" "Salle 3"
