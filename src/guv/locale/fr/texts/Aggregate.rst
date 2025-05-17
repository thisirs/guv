Agrégation d'un tableau provenant d'un fichier Excel/csv.

Les arguments ``left_on`` et ``right_on`` sont des noms de colonnes pour
réaliser une jointure : ``left_on`` est une colonne présente dans le fichier
central ``effectif.xlsx`` et ``right_on`` est une colonne du fichier à
agréger. Dans le cas où la jointure est plus complexe, on peut utiliser les
fonctions :func:`guv.helpers.id_slug` et :func:`guv.helpers.concat` (voir
Exemples) Dans le cas où ``left_on`` et ``right_on`` ont la même valeur, on
peut seulement spécifier ``on``.

``subset`` est une liste des colonnes à garder si on ne veut pas agréger la
totalité des colonnes, ``drop`` une liste des colonnes à enlever. ``rename``
est un dictionnaire des colonnes à renommer. ``read_method`` est un
*callable* appelé avec ``kw_read`` pour lire le fichier contenant le
*DataFrame* à agréger. ``preprocessing`` et ``postprocessing`` sont des
*callable* qui prennent en argument un *DataFrame* et en renvoie un et qui
réalise respectivement un pré-traitement sur le fichier à agréger ou un
post-traitement sur l'agrégation. ``merge_policy`` indique si on doit tenter
de fusionner des colonnes qui portent le même nom dans ``effectif.xlsx`` et
le fichier à agréger.

Parameters
----------

filename : :obj:`str`
    Le chemin du fichier csv/Excel à agréger.

left_on : :obj:`str`
    Le nom de colonne présent dans le fichier ``effectif.xlsx`` pour
    réaliser la jointure. On peut également utiliser les fonctions
    :func:`guv.helpers.id_slug` et :func:`guv.helpers.concat` pour une
    jointure prenant en compte plusieurs colonnes.

right_on : :obj:`str`
    Le nom de colonne présent dans le fichier à incorporer pour
    réaliser la jointure. On peut également utiliser les fonctions
    :func:`guv.helpers.id_slug` et :func:`guv.helpers.concat` pour une
    jointure prenant en compte plusieurs colonnes.

on : :obj:`str`
    Raccourci lorsque ``left_on`` et ``right_on`` ont la même
    valeur.

subset : :obj:`list`, optional
    Permet de sélectionner un nombre restreint de colonnes en
    spécifiant la liste. Par défaut, toutes les colonnes sont
    incorporées.

drop : :obj:`list`, optional
    Permet d'enlever des colonnes de l'agrégation.

rename : :obj:`dict`, optional
    Permet de renommer des colonnes après incorporation.

read_method : :obj:`callable`, optional
    Spécifie la fonction à appeler pour charger le fichier. Les
    fonctions Pandas ``pd.read_csv`` et ``pd.read_excel`` sont
    automatiquement sélectionnées pour les fichiers ayant pour
    extension ".csv" ou ".xlsx".

kw_read : :obj:`dict`, optional
    Les arguments nommés à utiliser avec la fonction
    ``read_method``. Par exemple, pour un fichier ".csv" on peut
    spécifier :

    .. code:: python

       kw_read={"header": None, "names": ["Courriel", "TP_pres"]}
       kw_read={"na_values": "-"}

preprocessing : :obj:`callable`, optional
    Pré-traitement à appliquer au *DataFrame* avant de l'intégrer.

postprocessing : :obj:`callable`, optional
    Post-traitement à appliquer au *DataFrame* après intégration du fichier.

merge_policy : :obj:`str`, optional
    Stratégie de fusion de colonnes lorsqu'elles portent le même nom.

    - ``merge``: On fusionne uniquement si les colonnes se complètent par
      rapport au valeurs NA
    - ``replace``: Toutes les valeurs non-NA provenant du fichier à agréger
      sont utilisées.
    - ``fill_na``: Seules les valeurs NA de la colonne ``effectif.xlsx``
      sont remplacées
    - ``keep``: On garde la colonne provenant de ``effectif.xlsx`` sans
      aucun changement
    - ``erase``: On écrase la colonne avec la colonne provenant du fichier à
      agréger

Examples
--------

- Agrégation des colonnes d'un fichier csv suivant la colonne
  ``email`` du fichier csv et ``Courriel`` du fichier central :

  .. code:: python

     DOCS.aggregate(
         "documents/notes.csv",
         left_on="Courriel",
         right_on="email"
     )

- Agrégation de la colonne ``Note`` d'un fichier csv suivant la
  colonne ``email`` du fichier csv et ``Courriel`` du fichier
  central :

  .. code:: python

     DOCS.aggregate(
         "documents/notes.csv",
         left_on="Courriel",
         right_on="email",
         subset="Note"
     )

- Agrégation de la colonne ``Note`` renommée en ``Note_médian``
  d'un fichier csv suivant la colonne ``email`` du fichier csv et
  ``Courriel`` du fichier central :

  .. code:: python

     DOCS.aggregate(
         "documents/notes.csv",
         left_on="Courriel",
         right_on="email",
         subset="Note",
         rename={"Note": "Note_médian"}
     )

- Agrégation de la colonne ``Note`` suivant ``Courriel`` en
  spécifiant l'en-tête absente du fichier csv :

  .. code:: python

     DOCS.aggregate(
         "documents/notes.csv",
         on="Courriel",
         kw_read={"header": None, "names": ["Courriel", "Note"]},
     )

- Agrégation d'un fichier csv de notes suivant les colonnes ``Nom`` et
  ``Prénom`` en calculant un identifiant (slug) sur ces deux colonnes pour
  une mise en correspondance plus souple (robuste par rapport aux accents,
  majuscules, tirets,...) :

  .. code:: python

     from guv.helpers import id_slug
     DOCS.aggregate(
         "documents/notes.csv",
         left_on=id_slug("Nom", "Prénom"),
         right_on=id_slug("Nom", "Prénom")
     )

- Agrégation d'un fichier csv de notes suivant les colonnes ``Nom`` et
  ``Prénom`` en les concaténant car le fichier à agréger contient seulement
  une colonne avec ``Nom`` et ``Prénom`` :

  .. code:: python

     from guv.helpers import concat
     DOCS.aggregate(
         "documents/notes.csv",
         left_on=concat("Nom", "Prénom"),
         right_on="Nom_Prénom"
     )

