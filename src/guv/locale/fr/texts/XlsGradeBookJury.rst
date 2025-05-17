Fichier Excel pour la gestion d'un jury d'UV

Cette tâche permet de générer un fichier Excel pour la gestion d'un jury
d'UV/UE. L'argument optionnel ``--name`` permet de spécifier un nom au
fichier (par défaut "jury").

L'argument optionnel ``--config`` permet de spécifier un fichier pour
configurer les données nécessaires au jury. S'il n'est pas fourni, une
configuration sera demandée interactivement.

Plus précisément, le classeur créé contient deux feuilles avec sur la
première feuille :

- les colonnes nom, prénom et courriel du fichier central ``effectif.xlsx``
  telles que spécifiées dans ``config.py``
- les notes spécifiées dans le fichier de configuration via
  ``--config`` ou interactivement qui participent à la note finale,
- une colonne spéciale nommée "Note agrégée" contenant une note sur 20 avec
  une formule par défaut utilisant les coefficients et les notes maximales
  renseignées dans le fichier de configuration ou interactivement,
- une note ECTS (ABCDEF) automatiquement calculée représentant la note
  agrégée en fonction de percentiles,
- d'autres colonnes utiles pour le jury et qui ne sont pas des notes.

La deuxième feuille met à disposition des barres d'admission pour chaque
note, les coefficients de chaque note, les notes maximales pour chaque note
ainsi que les barres pour la conversion de la note agrégée en note ECTS
ainsi que quelques statistiques sur la répartition des notes.

Le fichier de configuration est un fichier au format YAML. Les notes devant
être utilisées sont listées dans la section ``grades``. On doit spécifier le
nom de la colonne avec ``name`` et optionnellement :

- une barre de passage avec ``passing grade``, par défaut -1,
- un coefficient avec ``coefficient``, par défaut 1,
- une note maximale avec ``maximum grade``, par défaut 20,

Les colonnes qui ne sont pas des notes peuvent être spécifiées avec
``others``. Par exemple :

.. code:: yaml

   grades:
     - name: grade1
       passing grade: 8
       coefficient: 2
     - name: grade2
     - name: grade3
   others:
     - info

La note ECTS et la note agrégée peuvent ensuite être facilement
incorporées au fichier central en renseignant la variable
``DOCS``.

.. code:: python

   DOCS.aggregate_jury("generated/jury_gradebook.xlsx")

{options}

Examples
--------

- Feuille de notes avec la note ``median``, la note ``final`` avec
  une barre à 6 et l'information ``Branche`` :

  .. code:: bash

     guv xls_grade_book_jury --config documents/config_jury.yml

  avec le fichier YAML contenant par exemple :

  .. code:: yaml

     grades:
       - name: quiz
         coefficient: 0.2
         maximum grade: 10
       - name: median
         coefficient: 0.3
       - name: final
         coefficient: 0.5
         passing grade: 6
     others:
       - Branche

