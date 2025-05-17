Fichier csv de groupes et groupements à charger sur Moodle pour les créer.

Il faut spécifier le nombre de groupes dans chaque groupement avec
l'argument ``-g`` et le nombre de groupements dans
``-G``.

Le nom des groupements est contrôlé par un modèle spécifié par
l'argument ``-F`` (par défaut "D##_P1"). Les remplacements
disponibles sont :

- ## : remplacé par des nombres
- @@ : remplacé par des lettres

Le nom des groupes est contrôlé par un modèle spécifié par
l'argument ``-f`` (par défaut "D##_P1_@"). Les remplacements
disponibles sont :

- # : remplacé par des nombres
- @ : remplacé par des lettres

{options}

Examples
--------

.. code:: bash

   guv csv_groups_groupings -G 3 -F Groupement_P1 -g 14 -f D##_P1_@
   guv csv_groups_groupings -G 2 -F Groupement_D1 -g 14 -f D1_P##_@
   guv csv_groups_groupings -G 2 -F Groupement_D2 -g 14 -f D2_P##_@
   guv csv_groups_groupings -G 2 -F Groupement_D3 -g 14 -f D3_P##_@

