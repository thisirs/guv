Agrégation du fichier central ``effectif.xlsx`` lui-même.

Il est parfois plus pratique d'ajouter soi-même des colonnes dans le fichier
central ``effectif.xlsx`` ou d'en modifier d'autres au lieu d'en ajouter
programmatiquement via ``DOCS.aggregate(...)`` par exemple. Comme *guv* ne
peut pas détecter de façon fiable les colonnes ajoutées ou modifiées, il
faut lui indiquer lesquelles via l'argument ``*columns``.

Parameters
----------

*columns : any number of :obj:`str`
    Les colonnes manuellement ajoutées ou modifiées à garder lors de la mise
    à jour du fichier central.

