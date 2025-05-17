Fichier Excel de notes individuelles.

Cette tâche permet de générer un fichier Excel pour rentrer facilement des
notes avec un ou plusieurs barèmes détaillés. Le fichier Excel peut aussi
être divisé en plusieurs feuilles de calculs selon une colonne du fichier
``effectif.xlsx`` via l'argument ``--worksheets``. Dans chacune de ces
feuilles, les étudiants peuvent être ordonnés suivant l'argument
``--order-by``. On peut ajouter des colonnes supplémentaires à faire figurer
dans la première feuille avec l'argument ``--extra-cols``. Le ou les chemins
vers un fichier de barème détaillé peut être fourni via l'argument
``--marking-scheme``. Si l'argument n'est pas utilisé, les barèmes seront
demandés interactivement. Le fichier de barème doit être au format YAML. La
structure du devoir est spécifiée de manière arborescente avec une liste
finale pour les questions contenant les points accordés à cette question et
éventuellement le coefficient (par défaut 1) et des détails (ne figurant pas
dans le fichier Excel). Par exemple :

.. code:: yaml

   Exercice 1:
     Question 1:
       - points: 1
   Problème:
     Partie 1:
       Question 1:
         - points: 2
       Question 2:
         - points: 2
         - coeff: 3
       Question 3:
         - points: 2
         - détails: |
             Question difficile, ne pas noter trop sévèrement.
     Partie 2:
       Question 1:
         - points: 2
       Question 2:
         - points: 2


Les notes finales peuvent ensuite être facilement incorporées au
fichier central en renseignant la variable ``DOCS``.

{options}

Examples
--------

- Fichier de notes avec un barème à définir interactivement sur une seule
  feuille Excel :

  .. code:: bash

     guv xls_grade_book_no_group --name Devoir1

- Fichier de notes pour un devoir en fournissant un barème et en divisant
  par groupe de TD :

  .. code:: bash

     guv xls_grade_book_no_group \
       --name Devoir1 \
       --marking-scheme documents/barème_devoir1.yml \
       --worksheets TD

  avec le fichier YAML contenant par exemple :

  .. code:: yaml

     Exercice 1:
       Question 1:
         - points: 1
     Exercice 2:
       Question 1:
         - points: 1

- Fichier de notes pour une soutenance individuelle en divisant
  par jour de passage (colonne "Jour passage" dans
  ``effectif.xlsx``) et en ordonnant par ordre de passage
  (colonne "Ordre passage" dans ``effectif.xlsx``) :

  .. code:: bash

     guv xls_grade_book_no_group \
       --name Soutenance1 \
       --marking-scheme documents/barème_soutenance1.yml \
       --worksheets "Jour passage" \
       --order-by "Ordre passage"

  avec le fichier YAML contenant par exemple :

  .. code:: yaml

     Fond:
     Forme:

