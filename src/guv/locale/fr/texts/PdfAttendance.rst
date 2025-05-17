Fichier pdf de feuilles de présence.

Cette tâche génère un fichier pdf ou un fichier zip de fichiers
pdf contenant des feuilles de présence.

{options}

Examples
--------

- Feuille de présence nominative :

  .. code:: bash

     guv pdf_attendance --title "Examen"

- Feuilles de présence nominative par groupe de TP :

  .. code:: bash

     guv pdf_attendance --title "Examen de TP" --group TP

- Feuilles de présence sans les noms par groupe de TP :

  .. code:: bash

     guv pdf_attendance --title "Examen de TP" --group TP --blank

- Feuilles de présence nominative découpées pour trois salles :

  .. code:: bash

     guv pdf_attendance --title "Examen de TP" --count 24 24 24 --name "Salle 1" "Salle 2" "Salle 3"

