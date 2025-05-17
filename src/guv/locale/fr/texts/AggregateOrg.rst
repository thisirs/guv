Agrégation d'un fichier au format Org.

Le document à agréger est au format Org. Les titres servent de clé
pour l'agrégation et le contenu de ces titres est agrégé.

Parameters
----------

filename : :obj:`str`
    Le chemin du fichier Org à agréger.

colname : :obj:`str`
    Nom de la colonne dans lequel stocker les informations
    présentes dans le fichier Org.

on : :obj:`str`, optional
    Colonne du fichier ``effectif.xlsx`` servant de clé pour
    agréger avec les titres du fichier Org. Par défaut, les titres
    doivent contenir les nom et prénom des étudiants.

postprocessing : :obj:`callable`, optional
    Post-traitement à appliquer au *DataFrame* après intégration
    du fichier Org.

Examples
--------

- Agrégation d'un fichier avec les noms des étudiants pour titre :

  Le fichier Org :

  .. code:: text

     * Bob Morane
       Souvent absent
     * Untel
       Voir email d'excuse

  L'instruction d'agrégation :

  .. code:: python

     DOCS.aggregate_org("documents/infos.org", colname="Informations")

- Agrégation d'un fichier avec pour titres les éléments d'une
  colonne existante. Par exemple, on peut agréger les notes par
  groupe de projet prises dans le fichier Org. On spécifie la
  colonne contenant les groupes de projet "Projet1_Group".

  Le fichier Org :

  .. code:: text

     * Projet1_Group1
       A
     * Projet1_Group2
       B

  L'instruction d'agrégation :

  .. code:: python

     DOCS.aggregate_org("documents/infos.org", colname="Note projet 1", on="Project1_group")

