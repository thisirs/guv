Fichiers csv de groupes présents dans ``effectif.xlsx`` pour Moodle.

L'option ``--groups`` permet de sélectionner les colonnes de groupes à
exporter sous Moodle. Par défaut, les colonnes exportées sont les colonnes
``Cours``, ``TD`` et ``TP``.

L'option ``--long`` permet d'exporter les noms de groupes de TD/TP au format
long c'est à dire ``TP1`` et ``TD1`` au lieu de ``T1`` et ``D1``

L'option ``--single`` permet de ne générer qu'un seul fichier.

{options}

Examples
--------

.. code:: bash

   guv csv_groups --groups Groupe_Projet

