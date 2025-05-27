Agrège des données de groupes issue de l'activité "Choix de Groupe".

Le nom de la colonne des groupes étant toujours "Groupe", l'argument
``colname`` permet d'en spécifier un nouveau. Si la colonne existe déjà dans
le fichier central, il est possible de la sauvegarder avec l'option
``backup``.

Parameters
----------

filename : :obj:`str`
    Le chemin du fichier à agréger.

colname: :obj:`str`
    Le nom de la colonne de groupe où stocker les informations

backup : :obj:`bool`
    Sauvegarder la colonne avant tout changement


Examples
--------

.. code:: python

   DOCS.aggregate_moodle_groups("documents/Paper study groups.xlsx", "Paper")

