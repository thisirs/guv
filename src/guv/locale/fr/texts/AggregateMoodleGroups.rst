Agrège des données de groupes issue de l'activité "Choix de Groupe".

Le nom de la colonne des groupes étant toujours "Groupe", l'argument
``colname`` permet d'en spécifier un nouveau. Si la colonne existe déjà dans
le fichier central, il est possible de la sauvegarder avec l'option
``backup``.

Examples
--------

.. code:: python

   DOCS.aggregate_moodle_groups("documents/Paper study groups.xlsx", "Paper")

