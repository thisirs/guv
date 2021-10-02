=====
 guv
=====

**guv** est un outil en ligne de commande d'aide à la gestion d'une ou
plusieurs UV ou UE. Il permet de centraliser les informations concernant
une UV/UE et d'en incorporer facilement de nouvelles au travers de
fichiers de configuration. Il permet entre autres de créer des fichiers
iCal, des trombinoscopes, des feuilles de présences, des feuilles de
notes...

.. contents:: Sommaire
    :depth: 2

Installation
============

Il faut d'abord télécharger l'archive du projet sur Gitlab et
l'installer avec ``pip`` :

.. code:: bash

   pip install .

On peut également cloner le projet si ``git`` est installé comme suit :

.. code:: bash

   git clone git@gitlab.utc.fr:syrousse/guv.git
   cd guv
   pip install .

Un fichier de complétion de commandes est également disponible (voir
:ref:`fichier-de-complétion`).

Exemple rapide
==============

On commence par créer l'arborescence requise (voir
:ref:`création-de-larborescence` pour plus de détails) :

.. code:: bash

   guv createsemester P2021 --uv SY02 SY09
   cd P2021

Les variables ont été renseignées dans le fichier ``config.py`` du
semestre.

On renseigne ensuite dans le fichier ``config.py`` du semestre, le
chemin relatif du fichier pdf de la liste officielle des créneaux du
semestre :

.. code:: python

   CRENEAU_UV = "documents/Creneaux-UV-hybride-prov-V02.pdf"

On peut maintenant exécuter ``guv cal_uv`` dans le dossier du semestre
pour générer les calendriers hebdomadaires des UV.

Tutoriel
========

**guv** doit utiliser des fichiers fournis par l'administration
spécifique d'une UV ou pas pour créer de nouveaux fichiers. Pour cela,
**guv** s'appuie sur la bibliothèque Python ``doit`` qui est une
implémentation de type ``make``. À l'image de ``doit``, **guv** peut
exécuter des tâches et chaque appel à **guv** est de la forme :

.. code:: bash

   guv <une_tâche> <les arguments de la tâche>

**guv** travaille avec une arborescence prédéfinie. Les documents
spécifiques à une UV sont stockées dans un dossier d'UV. Tous les
dossiers d'UV sont stockés dans un dossier de semestre. Chaque dossier
d'UV contient un fichier nommé ``config.py`` pour configurer l'UV. Le
dossier de semestre contient également un dossier de configuration nommé
``config.py``.

.. _création-de-larborescence:

Création de l'arborescence
--------------------------

Pour créer cette arborescence ainsi que les fichiers de configuration,
préremplis on peut exécuter la commande suivante :

.. code:: bash

   guv createsemester P2020 --uv SY02 SY09

qui va créer un dossier de semestre nommé ``P2020`` contenant un fichier
de configuration prérempli ``config.py`` ainsi que des sous-dossiers
``generated`` et ``documents`` et deux dossiers d'UV nommés ``SY02`` et
``SY09`` contenant chacun leur fichier de configuration prérempli
également nommé ``config.py`` et des sous-dossiers ``generated`` et
``documents``. L'arborescence est ainsi la suivante :

.. code:: shell

   P2020
   ├── config.py
   ├── documents
   ├── generated
   ├── SY02
   │   ├── config.py
   │   ├── documents
   │   └── generated
   └── SY09
       ├── config.py
       ├── documents
       └── generated

Si on veut rajouter des dossiers d'UV à un dossier de semestre déjà
existant, on peut exécuter la commande suivante à l'intérieur d'un
dossier de semestre:

.. code:: bash

   cd P2020
   guv createuv SY19 AOS1

Configuration des fichiers ``config.py``
----------------------------------------

Le semestre ainsi que chacune des UV qu'il contient sont paramétrés par
des fichiers de configuration nommé ``config.py`` présent à la racine de
leur dossier respectif.

Fichier ``config.py`` de configuration de semestre
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Le fichier de configuration du semestre contient des informations
spécifiques à un semestre : liste des UV gérées, chemin vers le fichier
des créneaux fourni par l'administration, liste des plannings,
calendrier.


Configuration des plannings avec ``PLANNINGS``
++++++++++++++++++++++++++++++++++++++++++++++

Les plannings sont des périodes de temps sur un même semestre. Par
défaut, le planning ingénieur, qui porte le même nom que le semestre
est utilisé. Il est possible de configurer d'autres périodes de temps
pour un même semestre (pour gérer les trimestres des masters par
exemple).

La déclaration des plannings est controlée par la variable
``PLANNINGS`` qui est un dictionnaire dont les clés sont le nom des
plannings à paramétrer et les valeurs un dictionnaire de
caractéristiques.

Les caractéristiques nécessaires sont la liste des UV gérées par ce
planning, la date de début et la date de fin du planning.

Par exemple, on peut avoir la définition suivante :

.. code:: python

   from datetime import date
   PLANNINGS = {
       "P2020": {
           "UVS": ["SY09", "SY02"],
           "PL_BEG": date(2020, 2, 24),
           "PL_END": date(2020, 6, 27)
       }
   }

Configuration du planning ingénieur
+++++++++++++++++++++++++++++++++++

Afin de créer les créneaux de cours, il faut renseigner quelques
paramètres pour créer le planning ingénieur. Les dates de début et de
fin de période sont déjà renseignées dans la variable ``PLANNINGS``.

Les jours qui sont transformés en d'autres jours pour tenir compte
des jours fériés ou journées spéciales sont listés dans la variable
``TURN``. Par exemple, on peut spécifier

.. code:: python

   from datetime import date
   TURN = {
       date(2020, 5, 4): 'Vendredi',
       date(2020, 5, 12): 'Vendredi',
       date(2020, 5, 20): 'Jeudi',
       date(2020, 6, 4): 'Lundi'
   }

Les variables ``SKIP_DAYS_C``, ``SKIP_DAYS_D`` et ``SKIP_DAYS_T``
contiennent respectivement la liste des jours où il n'y a pas de
cours, TD, TP (première semaine, vacances, median, final...). Des
fonctions d'aide telles que ``skip_week``, ``skip_range`` sont mises
à disposition.

.. code:: python

   from guv.helpers import skip_week, skip_range

   # Première semaine sans TD/TP
   debut = skip_week(PLANNINGS["P2020"]['PL_BEG'])

   # Semaine des médians
   median = skip_range(date(2020, 4, 27), date(2020, 5, 4))

   # Vacances
   vacances_printemps = skip_range(date(2020, 4, 13), date(2020, 4, 18))

   # Semaine des finals
   final = skip_range(date(2020, 6, 19), date(2020, 6, 27))

   # Jours sautés pour Cours/TD/TP
   SKIP_DAYS_C = ferie + vacances_printemps + median + final
   SKIP_DAYS_D = ferie + vacances_printemps + debut + median + final
   SKIP_DAYS_T = ferie + vacances_printemps + debut + final


Configuration des créneaux
++++++++++++++++++++++++++

Les créneaux officiels portant sur toutes les UV de l'UTC durant une
semaine type sont renseignés dans un fichier pdf fourni par
l'administration et disponible `ici
<https://webapplis.utc.fr/ent/services/services.jsf?sid=578>`__. Il
faut renseigner son chemin relatif dans la variable ``CRENEAU_UV``.

Fichier ``config.py`` de configuration d'UV
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Le fichier de configuration d'une UV contient des informations
spécifiques à l'UV. Suivant les besoins, il faut fournir les chemins
vers des sources de données fournies par l'UTC, Moodle ou autres.

.. _ent-listing:

Fichier d'extraction de l'effectif d'une UV
+++++++++++++++++++++++++++++++++++++++++++

Le fichier de l'effectif officiel d'une UV est disponible sur l'ENT
sous la rubrique "Inscriptions aux enseignements - Liste des
étudiants inscrits" en cliquant sur "Extractions". Il s'agit d'un
fichier nommé ``extraction_enseig_note.XLS`` (même si c'est un
fichier csv). Il faut renseigner son chemin relatif dans la variable
``ENT_LISTING``. Il constitue la base du fichier central de l'UV
``effectif.xlsx``. Il crée les colonnes suivantes :

-  ``Nom``
-  ``Prénom``
-  ``Date de naissance``
-  ``Inscription``
-  ``Branche``
-  ``Semestre``
-  ``Dernier diplôme obtenu``
-  ``Courriel``
-  ``Login``
-  ``Tel. 1``
-  ``Tel. 2``

Fichier d'affectation aux Cours/TD/TP
+++++++++++++++++++++++++++++++++++++

Il s'agit du fichier fourni par l'administration qui précise les
affectations des étudiants aux différents créneaux de Cours/TD/TP. Il
est envoyé par courriel aux responsables d'UV. On peut renseigner son
chemin relatif au dossier d'UV dans la variable
``AFFECTATION_LISTING``. Il est agrégé de manière automatique au
fichier central de l'UV où il crée les colonnes suivantes :

- ``Name`` : Nom de l'étudiant présent dans le fichier d'affectation
- ``Cours`` : Groupe de cours (``C``, ``C1``, ``C2``)
- ``TD`` : Groupe de TD (``D1``, ``D2``,...)
- ``TP`` : Groupe de TP (``T1``, ``T2``, ``T1A``, ``T1B``,...)

De part sa nature, son agrégation peut donner lieu à des ambiguïtés
qui sont levées en interrogeant l'utilisateur (choix semaine A/B, nom
d'étudiant non reconnu).

Fichier de l'effectif de Moodle
+++++++++++++++++++++++++++++++

Des renseignements supplémentaires sont disponibles sur Moodle :
l'identifiant de connexion, le numéro d'identification, l'adresse
courriel (qui peut différer de l'adresse figurant dans l'effectif
officiel). Ces informations sont disponibles en exportant sous Moodle
une feuille de note (en plus des notes qui ne nous intéresse pas). Il
faut aller dans ``Configuration du carnet de notes`` et sélectionner
``Feuille de calcul Excel`` dans le menu déroulant et ensuite
``Télécharger``.

On renseigne le chemin relatif de ce fichier dans la variable
``MOODLE_LISTING``. Une fois incorporé, ce fichier crée les colonnes
suivantes :

- ``Prénom_moodle``
- ``Nom_moodle``
- ``Numéro d'identification``
- ``Adresse de courriel``

Fichier des tiers-temps
+++++++++++++++++++++++

Il s'agit d'un simple fichier texte avec commentaire éventuel listant
ligne par ligne les étudiants bénéficiant d'un tiers-temps. Il crée
la colonne ``tiers-temps`` dans le fichier central de l'UV.

On peut le renseigner dans la variable ``TIERS_TEMPS``. Par exemple :

.. code:: shell

   # Étudiants bénéficiant d'un tiers-temps
   Bob Arctor

Fichiers des changements de TD/TP
+++++++++++++++++++++++++++++++++

Il s'agit de fichiers de prise en compte des changements de groupes
de TD/TP par rapport au groupes officiels tels que décrits par le
fichier ``AFFECTATION_LISTING``.

Chaque ligne repère un changement qui est de la forme
``id1 --- id2``. Les identifiants peuvent être des adresses email ou
de la forme "nom prénom". L'identifiant ``id2`` peut également être
un identifiant de séance (``D1``, ``D2``, ``T1``, ``T2``,...) au cas où
il y a un transfert et non un échange.

On peut renseigner le chemin relatif vers ces fichiers dans les
variables ``CHANGEMENT_TD`` et ``CHANGEMENT_TP``.

Fichier d'information générale par étudiant
+++++++++++++++++++++++++++++++++++++++++++

Il arrive que l'on souhaite stocker d'autres informations de type
textuel sur un étudiant. On peut le renseigner dans la variable
``INFO_ETUDIANT``. C'est un fichier au format ``Org`` de la forme
suivante :

.. code:: org

   * Nom1 Prénom1
     texte1
   * Nom2 Prénom2
     texte2

Les informations sont incoporées dans une colonne nommée ``Info``.

Workflow classique
==================

Gestion d'une UV
----------------

Gestion des étudiants
---------------------

**guv** permet la gestion des étudiants de plusieurs UV/UE. Pour cela,
il est nécessaire de renseigner les variables ``ENT_LISTING`` (voir
:ref:`ent-listing`), ``AFFECTATION_LISTING`` et éventuellement
``MOODLE_LISTING``.

Ensuite en exécutant simplement **guv** sans argument dans le dossier
d'UV, le fichier central ``effectifs.xlsx`` regroupant ces
informations est créé. Ce fichier est regénéré à chaque fois qu'il y a
un changement dans les dépendances. Il ne faut donc jamais y rentrer
des informations manuellement. Pour incorporer des informations, voir
:ref:`incorporation`.

Gestion des intervenants
------------------------

**guv** offre également une gestion des intervenants dans les UV/UE.
Cela permet par exemple de générer des fichiers iCal par intervenant sur
tout un semestre, de générer un fichier récapitulatif des UTP
effectuées.

Pour cela, il faut remplir les fichiers ``planning_hebdomadaire.xlsx``
situés dans le sous-dossier ``documents`` de chaque UV/UE. Ces
fichiers sont automatiquement générés s'ils n'existent pas lorsqu'on
exécute simplement **guv** sans tâche particulière.

Les fichiers ``planning_hebdomadaire.xlsx`` contiennent toutes les
séances de l'UV/UE concernée d'après le fichier pdf renseigné dans
``CRENEAU_UV`` ou d'après le fichier Excel renseigné par
``CRENEAU_UE``. Il suffit de préciser le nom de l'intervenant dans la
colonne ``Intervenants`` et en supprimant éventuellement des créneaux
non retenus.

Interfaçage avec Moodle
-----------------------

**guv** permet d'agréger les informations issues de Moodle mais permet
également de créer des fichiers importables sur Moodle : fichier de
groupes, fichier de notes, restriction d'accès aux activités en fonction
du planning.

.. _incorporation:

Incorporation d'informations extérieures
----------------------------------------

Les informations concernant l'effectif d'une UV sont toutes
rassemblées dans un fichier central Excel situé à la racine de l'UV :
``effectifs.xlsx``. Un certain nombre d'informations y sont déjà
incorporées automatiquement : l'effectif officiel via la variable
``ENT_LISTING``, les affectations au Cours/TD/TP ainsi que les données
Moodle, les tiers-temps, les changements de TD/TP et les informations
par étudiant si elle ont été renseignées dans variables
correspondantes.

Il arrive qu'on dispose d'informations extérieures concernant les
étudiants (feuilles de notes Excel/csv, fichier csv de groupes
provenant de Moodle ou généré avec **guv**,...) et qu'on veuille les
incorporer au fichier central de l'UV. Pour cela, il faut renseigner
la variable ``AGGREGATE_DOCUMENTS``. La variable
``AGGREGATE_DOCUMENTS`` est une liste de listes de longueur 2. Chaque
liste de longueur 2 est composée d'un chemin vers un fichier à
incorporer et d'une fonction prenant en argument le fichier central
sous forme de *DataFrame* Pandas auquel incorporer le fichier et le
chemin du fichier à incorporer et retourne un *DataFrame* mis à jour
avec les nouvelles informations.

Par exemple, si on dispose d'un fichier ``notes.csv`` situé dans le
sous-dossier ``documents`` de l'UV et qu'on veut l'incorporer, on écrira
en toute généralité :

.. code:: python

   def fonction_qui_incorpore(df, file_path):
       # On incorpore le fichier `file_path` à `df` et on revoie `df`.

   AGGREGATE_DOCUMENTS = [
       [
           "documents/notes.csv",
           fonction_qui_incorpore
       ]
   ]

À la prochaine exécution de **guv** sans argument, la tâche par défaut
va reconstruire le fichier central et le fichier ``notes.csv`` sera
incorporé. Il reste à implémenter ``fonction_qui_incorpore`` qui
réalise l'incorporation. Cependant pour la plupart des usages, il
existe des fonctions spécialisées suivant le type d'information à
incorporer.

-  Fonction ``aggregate``

   .. autofunction:: guv.helpers.aggregate

-  Fonction ``fillna_column``

   .. autofunction:: guv.helpers.fillna_column

-  Fonction ``replace_regex``

   .. autofunction:: guv.helpers.replace_regex

-  Fonction ``replace_column``

   .. autofunction:: guv.helpers.replace_column

-  Fonction ``compute_new_column``

   .. autofunction:: guv.helpers.compute_new_column

-  Fonction ``aggregate_org``

   .. autofunction:: guv.helpers.aggregate_org

-  Fonction ``switch``

   .. autofunction:: guv.helpers.switch


Tâches
======

.. automodule:: guv.tasks
   :exclude-members:

Fichier de présence
-------------------

.. automodule:: guv.tasks.attendance
   :exclude-members:

.. autoclass:: guv.tasks.attendance.PdfAttendanceFull
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.students.XlsStudentDataMerge`

.. autoclass:: guv.tasks.attendance.PdfAttendance
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.students.XlsStudentDataMerge`

Fichier iCal
------------

.. automodule:: guv.tasks.ical
   :exclude-members:

.. autoclass:: guv.tasks.ical.IcalInst
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.instructors.AddInstructors`

Fichier trombinoscope
---------------------

.. automodule:: guv.tasks.trombinoscope
   :exclude-members:

.. autoclass:: guv.tasks.trombinoscope.PdfTrombinoscope
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.students.XlsStudentDataMerge`

Calendrier hebdomadaire
-----------------------

.. automodule:: guv.tasks.calendar
   :exclude-members:

.. autoclass:: guv.tasks.calendar.CalUv
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.instructors.XlsAffectation`

.. autoclass:: guv.tasks.calendar.CalInst
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.instructors.AddInstructors`

Étudiants
---------

.. automodule:: guv.tasks.students
   :exclude-members:

.. autoclass:: guv.tasks.students.CsvExamGroups
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.students.XlsStudentDataMerge`

.. autoclass:: guv.tasks.students.CsvMoodleGroups
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.students.XlsStudentDataMerge`

.. autoclass:: guv.tasks.students.ZoomBreakoutRooms
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.students.XlsStudentDataMerge`

Notes
-----

.. automodule:: guv.tasks.grades
   :exclude-members:

.. autoclass:: guv.tasks.grades.CsvForUpload
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.students.XlsStudentDataMerge`

.. autoclass:: guv.tasks.grades.XlsMergeFinalGrade
   :exclude-members:

.. autoclass:: guv.tasks.gradebook.XlsGradeBookJury
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.students.XlsStudentDataMerge`

.. autoclass:: guv.tasks.gradebook.XlsGradeBookNoGroup
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.students.XlsStudentDataMerge`

.. autoclass:: guv.tasks.gradebook.XlsGradeBookGroup
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.students.XlsStudentDataMerge`

.. autoclass:: guv.tasks.grades.YamlQCM
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.students.XlsStudentDataMerge`

.. autoclass:: guv.tasks.grades.XlsAssignmentGrade
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.instructors.XlsAffectation`
   - :class:`guv.tasks.students.XlsStudentDataMerge`

Intervenants
------------

.. automodule:: guv.tasks.instructors
   :exclude-members:

.. autoclass:: guv.tasks.instructors.XlsUTP
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.instructors.XlsAffectation`
   - :class:`guv.tasks.instructors.XlsInstructors`

Moodle
------

.. automodule:: guv.tasks.moodle
   :exclude-members:

.. autoclass:: guv.tasks.moodle.CsvGroups
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.students.XlsStudentDataMerge`

.. autoclass:: guv.tasks.moodle.CsvGroupsGroupings
   :exclude-members:

.. autoclass:: guv.tasks.moodle.HtmlInst
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.instructors.XlsAffectation`
   - :class:`guv.tasks.instructors.XlsInstructors`

.. autoclass:: guv.tasks.moodle.HtmlTable
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.instructors.AddInstructors`

.. autoclass:: guv.tasks.moodle.JsonRestriction
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.utc.CsvAllCourses`

.. autoclass:: guv.tasks.moodle.JsonGroup
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.students.XlsStudentDataMerge`

.. autoclass:: guv.tasks.moodle.CsvCreateGroups
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.students.XlsStudentDataMerge`

.. autoclass:: guv.tasks.moodle.FetchGroupId
   :exclude-members:

Tâches intermédiaires
=====================

Les tâches suivantes sont des tâches internes qu'on a normalement pas
besoin d'exécuter car elles sont des dépendances des tâches usuelles.

.. autoclass:: guv.tasks.utc.UtcUvListToCsv
   :exclude-members:

   Cette tâche est une dépendance pour les tâches suivantes :

   - :class:`guv.tasks.instructors.AddInstructors`
   - :class:`guv.tasks.instructors.XlsAffectation`

.. autoclass:: guv.tasks.utc.CsvAllCourses
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.instructors.AddInstructors`

   Cette tâche est une dépendance pour les tâches suivantes :

   - :class:`guv.tasks.moodle.JsonRestriction`

.. autoclass:: guv.tasks.students.CsvInscrits
   :exclude-members:

   Cette tâche est une dépendance pour les tâches suivantes :

   - :class:`guv.tasks.students.XlsStudentData`

.. autoclass:: guv.tasks.students.XlsStudentData
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.students.CsvInscrits`

   Cette tâche est une dépendance pour les tâches suivantes :

   - :class:`guv.tasks.students.XlsStudentDataMerge`

.. autoclass:: guv.tasks.students.XlsStudentDataMerge
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.students.XlsStudentData`

   Cette tâche est une dépendance pour les tâches suivantes :

   - :class:`guv.tasks.attendance.PdfAttendanceFull`
   - :class:`guv.tasks.attendance.PdfAttendance`
   - :class:`guv.tasks.grades.CsvForUpload`
   - :class:`guv.tasks.grades.XlsAssignmentGrade`
   - :class:`guv.tasks.grades.XlsGradeSheet`
   - :class:`guv.tasks.grades.YamlQCM`
   - :class:`guv.tasks.moodle.CsvCreateGroups`
   - :class:`guv.tasks.moodle.CsvGroups`
   - :class:`guv.tasks.moodle.JsonGroup`
   - :class:`guv.tasks.students.CsvExamGroups`
   - :class:`guv.tasks.students.CsvMoodleGroups`
   - :class:`guv.tasks.students.ZoomBreakoutRooms`
   - :class:`guv.tasks.trombinoscope.PdfTrombinoscope`

.. autoclass:: guv.tasks.instructors.XlsInstructors
   :exclude-members:

   Cette tâche est une dépendance pour les tâches suivantes :

   - :class:`guv.tasks.instructors.XlsInstDetails`
   - :class:`guv.tasks.instructors.XlsUTP`
   - :class:`guv.tasks.moodle.HtmlInst`

.. autoclass:: guv.tasks.instructors.AddInstructors
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.instructors.XlsAffectation`
   - :class:`guv.tasks.utc.UtcUvListToCsv`

   Cette tâche est une dépendance pour les tâches suivantes :

   - :class:`guv.tasks.ical.IcalInst`
   - :class:`guv.tasks.moodle.HtmlTable`
   - :class:`guv.tasks.utc.CsvAllCourses`
   - :class:`guv.tasks.calendar.CalInst`

.. autoclass:: guv.tasks.instructors.XlsInstDetails
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.instructors.XlsAffectation`
   - :class:`guv.tasks.instructors.XlsInstructors`

.. autoclass:: guv.tasks.instructors.XlsAffectation
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.utc.UtcUvListToCsv`

   Cette tâche est une dépendance pour les tâches suivantes :

   - :class:`guv.tasks.grades.XlsAssignmentGrade`
   - :class:`guv.tasks.moodle.HtmlInst`
   - :class:`guv.tasks.instructors.AddInstructors`
   - :class:`guv.tasks.instructors.XlsInstDetails`
   - :class:`guv.tasks.instructors.XlsUTP`
   - :class:`guv.tasks.calendar.CalUv`

Variables reconnues dans les fichiers ``config.py``
===================================================

Liste des variables reconnues dans les fichiers ``config.py`` de semestre
-------------------------------------------------------------------------

- ``UVS`` : Liste des UV ou UE gérées par **guv**. Cette variable est
  utilisée lorsqu'une tâche doit avoir accès à toutes les UV/UE gérées
  pour appliquer une même tâche à chaque.

- ``PLANNINGS`` : Dictionnaire des plannings avec leurs propriétés
  correspondantes.

- ``CRENEAU_UV`` : Chemin relatif vers le fichier pdf des créneaux des
  UVS ingénieur.

- ``CRENEAU_UE`` : Chemin relatif vers le fichier Excel des créneaux des
  UES de master.

- ``SELECTED_PLANNINGS`` : Liste des plannings à considérer. Par
  défaut, tous les plannings définis dans la variables ``PLANNINGS``
  sont considérés. La liste des plannings sélectionnés est notamment
  utilisée dans les tâches :class:`~guv.tasks.calendar.CalInst` et
  :class:`~guv.tasks.ical.IcalInst`.

- ``DEFAULT_INSTRUCTOR`` : Intervenant par défault utilisé dans les
  tâches :class:`~guv.tasks.calendar.CalInst` et
  :class:`~guv.tasks.ical.IcalInst`.

- ``DEBUG`` : Niveau de log.

- ``TURN`` : Dictionnaire des jours qui sont changés en d'autres jours
  de la semaine.

- ``SKIP_DAYS_C`` : Liste des jours (hors samedi/dimanche) où il n'y a
  pas cours.

- ``SKIP_DAYS_D`` : Liste des jours (hors samedi/dimanche) où il n'y a
  pas TD.

- ``SKIP_DAYS_T`` : Liste des jours (hors samedi/dimanche) où il n'y a
  pas TP.

- ``TASKS`` :

Liste des variables reconnues dans les fichiers ``config.py`` d'UV
------------------------------------------------------------------

- ``ENT_LISTING`` : Chemin relatif vers le fichier de l'UV tel que
  fourni par l'ENT.

- ``AFFECTATION_LISTING`` : Chemin relatif vers le fichier des
  créneaux de Cours/TD/TP.

- ``MOODLE_LISTING`` : Chemin relatif vers le fichier Moodle qu'on
  peut télécharger en allant dans Configuration du carnet de notes et
  en sélectionnant ``Feuille de calcul Excel`` dans le menu déroulant
  et ensuite ``Télécharger``.

- ``AGGREGATE_DOCUMENTS`` : Liste des documents à agréger au fichier
  central en plus des documents usuels.

Divers
======

Changement des chemins par défaut
---------------------------------

Beaucoup de tâches écrivent des fichiers avec un nom prédéfini dans un
dossier prédéfini. Il est possible de changer ces valeurs par défaut en
utilisant les attributs de classe ``target_name`` et ``target_dir`` de
la tâche correspondante. Par exemple, la tâche ``XlsStudentDataMerge``
est responsable de la création du fichier ``effectifs.xlsx`` dans le
dossier de l'UV.

Pour changer cela, on peut écrire le code suivant dans le fichier
``config.py`` de l'UV :

.. code:: python

   from guv.tasks import XlsStudentDataMerge
   XlsStudentDataMerge.target_name = "info.xlsx"
   XlsStudentDataMerge.target_dir = "documents"

L'effectif sera alors écrit dans le dossier ``documents`` avec le nom
``info.xlsx``.

Création d'une tâche
--------------------

Il est possible de créer ses propres tâches assez facilement. La
variable ``TASKS`` dans les fichiers de configuration est prévue à cet
effet. Il s'agit d'une liste de chemins vers des fichiers Python
définissant des tâches.

On peut distinguer deux types de tâches différentes qui doivent hériter
de deux classes différentes :

-  les tâches non spécifiques à une UV ou un groupe d'UV qui doivent
   hériter de la classe ``TaskBase``. On trouve par exemple :

   -  les tâches "par intervenants": calendrier hebdomadaire
   -  la tâche de création de tous les créneaux de Cours/TP/TD à l'UTC

-  les tâches spécifiques à une UV qui doivent hériter de la classe
   ``UVTask``. Ce sont les plus courantes et les plus utilisées, on
   trouve par exemple :

   -  le trombinoscope de l'effectif de l'UV
   -  les feuilles de présence concernant les TD d'une UV

   Dans les deux cas, deux méthodes doivent ensuite être implémentées :

   -  la méthode ``setup`` qui doit définir les attributs ``target`` et
      ``file_dep`` qui définissent la cible à créer ainsi que les
      dépendances utilisées pour créer cette cible.
   -  la méthode ``run`` qui effectue la tâche proprement dite en créant
      ``target`` avec les fichiers ``file_dep``.

Tâche non spécifique à une UV
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pour créer une tâche non spécifique à une UV, il faut hériter de la
classe ``TaskBase``. Les attributs de classe utiles sont :

-  ``target_dir``: le dossier relatif au semestre où le fichier cible
   sera placé.

-  ``target_name``: le nom de la cible créée

-  ``always_make``: la ou les cibles doivent doit être reconstruites
   même si les dépendances n'ont pas changé

   .. code:: python

      from guv.tasks.base import TaskBase

      class MaTache(TaskBase):
          def setup(self):
              super().setup()
              self.target = "result"
              self.file_dep = ["dependance1", "dependance2"]

          def run(self):
              print("Run")

Tâche spécifique à une UV
~~~~~~~~~~~~~~~~~~~~~~~~~

Les tâches spécifiques sont les plus courantes. Pour les créer, il faut
hériter de la classe ``UVTask``. Les attributs de classe utiles sont :

-  ``unique_uv``: la tâche ne peut être exécutée que pour une seule UV à
   la fois

-  ``target_dir``: le dossier relatif à l'UV où les fichiers utiles
   seront placés

-  ``target_name``: le nom du fichier créé

-  ``always_make``: la ou les cibles doivent doit être reconstruites
   même si les dépendances n'ont pas changé

   Comme il s'agit d'une tâche spécifique à une UV, les attributs ``uv``
   et ``planning`` sont disponibles depuis les méthodes ``setup`` et
   ``run``.

   Par exemple :

   .. code:: python

      from guv.tasks.base import UVTask

      class MaTache(UVTask):
          def setup(self):
              super().setup()
              print(f"Création de la tâche {self.name} pour l'UV {self.uv}")
              self.target = "file_result"
              self.file_dep = ["file1", "file2"]

          def run(self):
              print(f"Création de la cible {self.target}")

Autres classes
~~~~~~~~~~~~~~

La classe ``CliArgsMixin`` permet de paramétrer et de rentre
disponible pour les méthodes ``setup`` et ``run`` les arguments
fournis en ligne de commande. Il n'y a pas de méthode à implémenter,
juste une variable de classe ``cli_args`` à spécifier. La variable
``cli_args`` est un tuple contenant les arguments spécifiés avec la
fonction ``argument``.

.. code:: python

   from guv.utils import argument

   class MaTache(CliArgsMixin, UVTask):
       cli_args = (
           argument(
               "-a",
               "--aa",
           ),
       )

       def setup(self):
           super().setup()
           ...
           self.parse_args())
           ...

       def run(self):
           pass

Les spécifications à l'intérieur de la fonction ``argument`` sont les
mêmes que pour ``argparse``.

.. _fichier-de-complétion:

Fichier de complétion
---------------------

Des fichiers de complétion pour ``zsh`` et ``bash`` sont disponibles
dans le sous-dossier ``data``. Pour un système type Unix et le shell
``zsh``, on peut utiliser les commandes suivantes :

.. code:: bash

   mkdir -p ~/.zsh/completions
   cp $(python -c "import guv; print(guv.__path__[0])")/data/_guv_zsh ~/.zsh/completions/_guv

Si des tâches supplémentaires ont été ajoutées avec la variable
``TASKS``, il est possible de mettre à jour les fichiers de complétion.
Il faut d'abord installer la bibliothèque ``shtab`` et exécuter la
commande suivante dans le dossier du semestre.

.. code:: bash

   shtab --shell=zsh guv.runner.get_parser_shtab > ~/.zsh/completions/_guv

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
