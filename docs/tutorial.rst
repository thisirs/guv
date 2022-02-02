Configuration de base
=====================

**guv** doit utiliser des fichiers fournis par l'administration qui
sont spécifiques d'une UV ou pas pour créer de nouveaux fichiers. Pour
cela, **guv** s'appuie sur la bibliothèque Python ``doit`` qui est une
implémentation de type ``make``. À l'image de ``doit``, **guv** peut
exécuter des tâches et chaque appel à **guv** est de la forme :

.. code:: bash

   guv <une_tâche> <les arguments de la tâche>

Lorsque la configuration de base est effective, les tâches suivantes
sont accessibles :

- :class:`guv.tasks.attendance.PdfAttendanceFull`
- :class:`guv.tasks.attendance.PdfAttendance`
- :class:`guv.tasks.grades.CsvForUpload`
- :class:`guv.tasks.grades.XlsAssignmentGrade`
- :class:`guv.tasks.gradebook.XlsGradeBookJury`
- :class:`guv.tasks.gradebook.XlsGradeBookGroup`
- :class:`guv.tasks.gradebook.XlsGradeBookNoGroup`
- :class:`guv.tasks.grades.YamlQCM`
- :class:`guv.tasks.ical.IcalUv`
- :class:`guv.tasks.moodle.CsvCreateGroups`
- :class:`guv.tasks.moodle.CsvGroups`
- :class:`guv.tasks.moodle.JsonGroup`
- :class:`guv.tasks.students.CsvExamGroups`
- :class:`guv.tasks.students.CsvMoodleGroups`
- :class:`guv.tasks.students.ZoomBreakoutRooms`
- :class:`guv.tasks.trombinoscope.PdfTrombinoscope`

**guv** travaille avec une arborescence prédéfinie. Les documents
spécifiques à une UV sont stockées dans un dossier d'UV. Tous les
dossiers d'UV sont stockés dans un dossier de semestre. Chaque dossier
d'UV contient un fichier nommé ``config.py`` pour configurer l'UV. Le
dossier de semestre contient également un dossier de configuration nommé
``config.py``.

.. _création-de-larborescence:

Création de l'arborescence
--------------------------

Pour créer cette arborescence ainsi que les fichiers de configuration
préremplis on peut exécuter la commande suivante :

.. code:: bash

   guv createsemester P2022 --uv SY02 SY09

qui va créer un dossier de semestre nommé ``P2022`` contenant un
fichier de configuration prérempli ``config.py`` (voir
:ref:`conf-semester` pour sa configuration) ainsi que des
sous-dossiers ``generated`` et ``documents`` et deux autres dossiers
d'UV nommés ``SY02`` et ``SY09`` contenant chacun leur fichier de
configuration prérempli également nommé ``config.py`` (voir
:ref:`conf-UV` pour sa configuration) ainsi que des sous-dossiers
``generated`` et ``documents``. L'arborescence est alors la suivante :

.. code:: shell

   P2022
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

   cd P2022
   guv createuv SY19 AOS1

Pour que l'UV soit effectivement prise en compte par **guv**, il faut
ensuite la déclarer dans le fichier ``config.py`` du semestre avec
la variable ``UVS`` et lui associer un planning dans ``PLANNINGS``.

.. _conf-semester:

Fichier ``config.py`` de configuration de semestre
--------------------------------------------------

Le fichier de configuration du semestre contient des informations
spécifiques à un semestre :

- liste des UV/UE gérées via la variable ``UVS``,
- chemin vers le fichier des créneaux fourni par l'administration, via
  la variable ``CRENEAU_UV``,
- liste des plannings via la variable ``PLANNINGS``,
- information de calendrier avec les variables ``TURN``,
  ``SKIP_DAYS_C``, ``SKIP_DAYS_D``, ``SKIP_DAYS_T``

Si l'arborescence a été créée avec la tâche ``createsemester`` et un
nom de semestre reconnu par **guv** (de type A2021, P2022,...) les
variables ``PLANNINGS``, ``TURN``, ``SKIP_DAYS_C``, ``SKIP_DAYS_D``,
``SKIP_DAYS_T`` sont automatiquement renseignées. Si en plus les
dossiers d'UV ont été créés avec l'option ``--uv``, la variable
``UVS`` est aussi renseignée et on peut sauter les deux sections
suivantes.

Configuration des plannings avec ``PLANNINGS``
++++++++++++++++++++++++++++++++++++++++++++++

Les plannings sont des périodes de temps sur un même semestre. Par
défaut, le planning ingénieur, qui porte le même nom que le semestre
est utilisé. Il est possible de configurer d'autres périodes de temps
pour un même semestre (pour gérer les trimestres des masters par
exemple).

La déclaration des plannings est contrôlée par la variable
``PLANNINGS`` qui est un dictionnaire dont les clés sont le nom des
plannings à paramétrer et les valeurs un dictionnaire de
caractéristiques.

Les caractéristiques nécessaires sont la liste des UV gérées par ce
planning, la date de début et la date de fin du planning.

Si l'arboresence a été créée avec la tâche ``createsemester`` et que
le nom du semestre est reconnu, la variable ``PLANNINGS`` est
automatiquement remplie.

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
Si l'arboresence a été créée avec la tâche ``createsemester`` et que
le nom du semestre est reconnu, les autres variables du planning
ingénieur sont automatiquement remplies.

Sinon, il faut préciser les jours qui sont transformés en d'autres
jours pour tenir compte des jours fériés ou journées spéciales. Ils
sont listés dans la variable ``TURN``. Par exemple, on peut spécifier

.. code:: python

   from datetime import date
   TURN = {
       date(2020, 5, 4): 'Vendredi',
       date(2020, 5, 12): 'Vendredi',
       date(2020, 5, 20): 'Jeudi',
       date(2020, 6, 4): 'Lundi'
   }

Le 4 mai et le 12 mai sont donc un vendredi, le 20 mai est un jeudi et
le 4 juin est un lundi.

Il faut également renseigner les variables ``SKIP_DAYS_C``,
``SKIP_DAYS_D`` et ``SKIP_DAYS_T`` qui contiennent respectivement la
liste des jours où il n'y a pas de cours, TD, TP (première semaine,
vacances, median, final...). Des fonctions d'aide telles que
``skip_week``, ``skip_range`` sont mises à disposition.

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

.. _conf_creneau:

Configuration des créneaux
++++++++++++++++++++++++++

Les créneaux officiels portant sur toutes les UV de l'UTC durant une
semaine type sont renseignés dans un fichier pdf fourni par
l'administration et disponible `ici
<https://webapplis.utc.fr/ent/services/services.jsf?sid=578>`__. Il
faut le télécharger et renseigner son chemin relatif dans la variable
``CRENEAU_UV`` afin que **guv** ait connaissance des créneaux des UV.

.. _conf-UV:

Fichier ``config.py`` de configuration d'UV
-------------------------------------------

Le fichier de configuration d'une UV est situé à la racine du dossier
de l'UV/UE et contient des informations spécifiques à l'UV/UE. Il faut
obligatoirement indiquer à **guv** le chemin relatif vers le fichier
d'extraction de l'effectif de l'UV/UE (voir :ref:`ent-listing`).

Un autre fichier important est le fichier d'affectation aux
Cours/TD/TP (voir :ref:`affectation`) si il est disponible.

Il existe d'autres variables permettant d'ajouter d'autres
informations comme les informations Moodle, les changements de TD/TP
mais elles sont facultatives.

Lorsque les modifications du fichier ``config.py`` ont été faites, il
suffit d'exécuter la commande ``guv`` sans argument dans le dossier
d'UV/UE pour que les différentes informations soient incorporées à un
fichier central nommé ``effectif.xlsx`` (ainsi qu'une version csv)
situé à la racine du dossier d'UV/UE.

Le fichier ``effectif.xlsx`` est regénéré à chaque fois qu'il y a un
changement dans les dépendances. Il ne faut donc jamais y rentrer des
informations manuellement. Pour incorporer des informations, voir
:ref:`incorporation`.

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

.. _affectation:

Fichier d'affectation aux Cours/TD/TP
+++++++++++++++++++++++++++++++++++++

Il s'agit du fichier fourni par l'administration qui précise les
affectations des étudiants aux différents créneaux de Cours/TD/TP. Il
est envoyé par courriel aux responsables d'UV. Il faut le copier tel
quel dans un fichier et renseigner son chemin relatif au dossier d'UV
dans la variable ``AFFECTATION_LISTING``. Il est agrégé de manière
automatique au fichier central de l'UV où il crée les colonnes
suivantes :

- ``Name`` : Nom de l'étudiant présent dans le fichier d'affectation
- ``Cours`` : Groupe de cours (``C``, ``C1``, ``C2``)
- ``TD`` : Groupe de TD (``D1``, ``D2``,...)
- ``TP`` : Groupe de TP (``T1``, ``T2``, ``T1A``, ``T1B``,...)

De part sa nature, son agrégation peut donner lieu à des ambiguïtés
qui sont levées en interrogeant l'utilisateur (choix semaine A/B, nom
d'étudiant non reconnu).

.. _moodle-listing:

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
ligne par ligne les étudiants bénéficiant d'un tiers-temps. Il crée la
colonne ``tiers-temps`` dans le fichier central ``effectifs.xlsx`` de
l'UV.

On peut le renseigner dans la variable ``TIERS_TEMPS``. Par exemple :

.. code:: shell

   # Étudiants bénéficiant d'un tiers-temps
   Bob Arctor

Fichiers des changements de TD/TP
+++++++++++++++++++++++++++++++++

Il s'agit de fichiers de prise en compte des changements de groupes de
TD/TP par rapport au groupes officiels tels que décrits par le fichier
``AFFECTATION_LISTING`` et présents dans les colonnes "TD" et "TP" du
fichier ``effectifs.xlsx``.

Chaque ligne repère un changement qui est de la forme
``id1 --- id2``. Les identifiants peuvent être des adresses courriel ou
de la forme "nom prénom". L'identifiant ``id2`` peut également être
un identifiant de séance (``D1``, ``D2``, ``T1``, ``T2``,...) au cas où
il y a un transfert et non un échange.

Par exemple, dans le fichier pointé par ``CHANGEMENT_TD`` :

.. code:: text

   # Échange autorisé
   Ryland Grace --- Guy Montag

   # Incompatibilité Master
   Mycroft Canner --- D1

On peut renseigner le chemin relatif vers ces fichiers dans les
variables ``CHANGEMENT_TD`` et ``CHANGEMENT_TP``.

Fichier d'information générale par étudiant
+++++++++++++++++++++++++++++++++++++++++++

Il arrive que l'on souhaite stocker d'autres informations de type
textuel sur un étudiant. On peut le renseigner dans la variable
``INFO_ETUDIANT``. C'est un fichier au format ``Org`` de la forme
suivante :

.. code:: text

   * Nom1 Prénom1
     texte1
   * Nom2 Prénom2
     texte2

Les informations sont incoporées dans une colonne nommée ``Info``.

.. _incorporation:

Incorporation d'informations extérieures
++++++++++++++++++++++++++++++++++++++++

Les informations concernant l'effectif d'une UV sont toutes
rassemblées dans un fichier central Excel situé à la racine de l'UV :
``effectifs.xlsx``. Un certain nombre d'informations y sont déjà
incorporées automatiquement : l'effectif officiel via la variable
``ENT_LISTING``, les affectations au Cours/TD/TP ainsi que les données
Moodle, les tiers-temps, les changements de TD/TP et les informations
par étudiant si elles ont été renseignées dans les variables
correspondantes.

Il arrive qu'on dispose d'informations extérieures concernant les
étudiants (feuilles de notes Excel/csv, fichier csv de groupes
provenant de Moodle ou généré avec **guv**,...) et qu'on veuille les
incorporer au fichier central de l'UV. Pour cela, il faut décrire les
agrégations dans le fichier de configuration d'UV/UE à l'aide d'un
objet de type ``Documents`` impérativement appelé ``DOCS`` :

.. code:: python

   from guv.helpers import Documents
   DOCS = Documents()

Pour déclarer une incorporation, on utiliser la méthode ``add`` sur
``DOCS`` :

.. automethod:: guv.helpers.Documents.add

À la prochaine exécution de **guv** sans argument, la tâche par défaut
va reconstruire le fichier central et le fichier ``notes.csv`` sera
incorporé. Il reste à implémenter ``fonction_qui_incorpore`` qui
réalise l'incorporation. Cependant pour la plupart des usages, il
existe des fonctions spécialisées suivant le type d'information à
incorporer.

Pour incorporer des fichiers sous forme de tableau csv/Excel, on
utilise ``aggregate``. On a alors

.. code:: python

   DOCS.aggregate("documents/notes.csv", on="Courriel")

.. automethod:: guv.helpers.Documents.aggregate

Lorsque les fichiers sont encore plus spécifiques, on peut utiliser
les fonctions suivantes :

- Pour un fichier de notes issu de Moodle :

  .. automethod:: guv.helpers.Documents.aggregate_moodle_grades

- Pour un fichier de jury issu de la tâche
  :class:`~guv.tasks.gradebook.XlsGradeBookJury`

  .. automethod:: guv.helpers.Documents.aggregate_jury

Pour incorporer des fichiers au format Org, on utilise
``aggregate_org`` :

.. automethod:: guv.helpers.Documents.aggregate_org

Pour créer/modifier le fichier central sans utiliser de fichier tiers,
on peut utiliser les fonctions suivantes :

-  Fonction ``fillna_column``

   .. automethod:: guv.helpers.Documents.fillna_column

-  Fonction ``replace_regex``

   .. automethod:: guv.helpers.Documents.replace_regex

-  Fonction ``replace_column``

   .. automethod:: guv.helpers.Documents.replace_column

-  Fonction ``switch``

   .. automethod:: guv.helpers.Documents.switch

-  Fonction ``apply_df``

   .. automethod:: guv.helpers.Documents.apply_df

-  Fonction ``apply_column``

   .. automethod:: guv.helpers.Documents.apply_column

-  Fonction ``apply_cell``

   .. automethod:: guv.helpers.Documents.apply_cell

-  Fonction ``compute_new_column``

   .. automethod:: guv.helpers.Documents.compute_new_column

Configurations supplémentaires
==============================

Gestion des intervenants
------------------------

**guv** offre également une gestion des intervenants dans les UV/UE.
Cela permet par exemple de générer des fichiers iCal par intervenant
sur tout un semestre, de générer un fichier récapitulatif des UTP
effectuées.

Pour cela, il faut remplir les fichiers ``planning_hebdomadaire.xlsx``
situés dans le sous-dossier ``documents`` de chaque UV/UE. Ces
fichiers sont automatiquement générés s'ils n'existent pas lorsqu'on
exécute simplement ``guv`` sans argument dans le dossier de semestre.

Les fichiers ``planning_hebdomadaire.xlsx`` contiennent toutes les
séances de l'UV/UE concernée d'après le fichier pdf renseigné dans
``CRENEAU_UV``.

Si l'UV/UE n'est pas répertoriée dans le fichier pdf, il s'agit très
probablement d'une UE. Un fichier Excel vide avec en-tête est alors
créé et il faut renseigner manuellement les différents créneaux.

Dès lors, on peut utiliser les tâches suivantes :

- :class:`guv.tasks.instructors.XlsUTP`
- :class:`guv.tasks.calendar.CalInst`
- :class:`guv.tasks.ical.IcalInst`
- :class:`guv.tasks.calendar.CalUv`
- :class:`guv.tasks.moodle.HtmlInst`
- :class:`guv.tasks.moodle.HtmlTable`

