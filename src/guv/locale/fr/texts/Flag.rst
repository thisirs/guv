Signaler une liste d'étudiants dans une nouvelle colonne.

Le document à agréger est une liste de noms d'étudiants affichés
ligne par ligne.

Parameters
----------

filename_or_string : :obj:`str`
    Le chemin du fichier à agréger ou directement le texte du fichier.

colname : :obj:`str`
    Nom de la colonne dans laquelle mettre le drapeau.

flags : :obj:`str`, optional
    Les deux drapeaux utilisés, par défaut "Oui" et vide.

Examples
--------

Agrégation d'un fichier avec les noms des étudiants pour titre :

Le fichier "tiers_temps.txt" :

.. code:: text

   # Des commentaires
   Bob Morane

   # Robuste à la permutation circulaire et à la casse
   aRcTor BoB

L'instruction d'agrégation :

.. code:: python

   DOCS.flag("documents/tiers_temps.txt", colname="Tiers-temps")

