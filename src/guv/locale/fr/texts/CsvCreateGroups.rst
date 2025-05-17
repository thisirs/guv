Création aléatoire de groupes d'étudiants prêt à charger sous Moodle.

Cette tâche crée un fichier csv d'affectation des étudiants à un
groupe directement chargeable sous Moodle. Si l'option
``--grouping`` est spécifiée les groupes sont créés à l'intérieur
de chaque sous-groupe (de TP ou TD par exemple).

Le nombre de groupes créés (au total ou par sous-groupes suivant
``--grouping``) est contrôlé par une des options mutuellement
exclusives ``--proportions``, ``--group-size`` et
``--num-groups``. L'option ``--proportions`` permet de spécifier
un nombre de groupes via une liste de proportions. L'option
``--group-size`` permet de spécifier la taille maximale de chaque
groupe. L'option ``--num-groups`` permet de spécifier le nombre de
sous-groupes désirés.

Le nom des groupes est contrôlé par l'option ``--template``. Les
remplacements suivants sont disponibles à l'intérieur de
``--template`` :

- ``{title}`` : remplacé par le titre (premier argument)
- ``{grouping_name}`` : remplacé par le nom du sous-groupe à
  l'intérieur duquel on construit des groupes (si on a spécifié
  ``--grouping``)
- ``{group_name}`` : nom du groupe en construction (si on a
  spécifié ``--names``)
- ``#`` : numérotation séquentielle du groupe en construction (si
  ``--names`` n'est pas spécifié)
- ``@`` : lettre séquentielle du groupe en construction (si
  ``--names`` n'est pas spécifié)

L'option ``--names`` peut être une liste de noms à utiliser ou un
fichier contenant une liste de noms ligne par ligne. Il sont pris
aléatoirement si on spécifie le drapeau ``--random``.

Le drapeau ``--global`` permet de ne pas remettre à zéro la
génération des noms de groupes lorsqu'on change le groupement à
l'intérieur duquel on construit des groupes (utile seulement si on
a spécifié ``--grouping``).

Par défaut, la liste des étudiants est triée aléatoirement avant
de créer des groupes de manière contiguë. Si on veut créer des
groupes par ordre alphabétique, on peut utiliser ``--ordered``. On
peut également fournir une liste de colonnes selon lesquelles
trier.

On peut indiquer des contraintes dans la création des groupes avec l'option
``--other-groups`` qui spécifie des noms de colonnes de groupes déjà formés
qu'on va s'efforcer de ne pas reformer. On peut également indiquer des
affinités dans la création des groupes avec l'option ``--affinity-groups``
qui spécifie des noms de colonnes de groupes déjà formés qu'on va s'efforcer
de reformer à nouveau.

{options}

Examples
--------

- Faire des trinômes à l'intérieur de chaque sous-groupe de TD :

  .. code:: bash

     guv csv_create_groups Projet1 -G TD --group-size 3

- Faire des trinômes à l'intérieur de chaque sous-groupe de TD en
  s'efforçant de choisir des nouveaux trinômes par rapport à la colonne
  ``Projet1`` :

  .. code:: bash

     guv csv_create_groups Projet2 -G TD --group-size 3 --other-groups Projet1

- Partager en deux chaque sous-groupe de TD avec des noms de groupes
  de la forme D1i, D1ii, D2i, D2ii... :

  .. code:: bash

     guv csv_create_groups HalfGroup -G TD --proportions .5 .5 --template '{grouping_name}{group_name}' --names i ii

- Partager l'effectif en deux parties selon l'ordre alphabétique
  avec les noms de groupes ``First`` et ``Second`` :

  .. code:: bash

     guv csv_create_groups Half --proportions .5 .5 --ordered --names First Second --template '{group_name}'

.. rubric:: Remarques

Afin qu'il soit correctement chargé par Moodle, le fichier ne
contient pas d'en-tête spécifiant le nom des colonnes. Pour
agréger ce fichier de groupes au fichier central, il faut donc
utiliser l'argument ``kw_read`` comme suit :

.. code:: python

   DOCS.aggregate(
       "generated/Projet1_groups.csv",
       on="Courriel",
       kw_read={"header": None, "names": ["Courriel", "Groupe P1"]},
   )

