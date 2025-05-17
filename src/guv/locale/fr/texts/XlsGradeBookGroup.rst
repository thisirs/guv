Fichier Excel de notes par groupe.

Cette tâche permet de créer un fichier Excel pour attribuer des notes par
groupes évitant ainsi de recopier la note pour chaque membre du groupe. Les
groupes d'étudiants sont spécifiés par l'argument ``--group-by``. Un ou
plusieurs barèmes détaillés peuvent être fournis via l'argument
``--marking-scheme``. Le fichier Excel peut aussi être divisé en plusieurs
feuilles de calculs selon une colonne du fichier ``effectif.xlsx`` via
l'argument ``--worksheets``. Dans chacun des groupes, les étudiants peuvent
être ordonnés suivant l'argument ``--order-by``. On peut ajouter des
colonnes supplémentaires à faire figurer dans la première feuille avec
l'argument ``--extra-cols``. Le ou les chemins vers un fichier de barème
détaillé peut être fourni via l'argument ``--marking-scheme``. Si l'argument
n'est pas utilisé, les barèmes seront demandés interactivement. Le fichier
de barème doit être au format YAML. La structure du devoir est spécifiée de
manière arborescente avec une liste finale pour les questions contenant les
points accordés à cette question et éventuellement le coefficient (par
défaut 1) et des détails (ne figurant pas dans le fichier Excel). Par
exemple :

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

Fichier de notes par groupe de projet :

.. code:: bash

   guv xls_grade_book_group \
     --name Devoir1 \
     --marking-scheme documents/barème_devoir1.yml \
     --group-by 'Groupe Projet'

avec le fichier YAML contenant par exemple :

.. code:: yaml

   Exercice 1:
     Question 1:
       - points: 1
   Exercice 2:
     Question 1:
       - points: 1

