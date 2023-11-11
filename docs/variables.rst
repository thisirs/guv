Liste des variables reconnues dans les fichiers ``config.py`` de semestre
-------------------------------------------------------------------------

- ``UVS`` : Liste des UV ou UE gérées par **guv**. Si une UV/UE n'est
  pas renseignée dans cette liste, elle ne sera pas reconnue par
  **guv**.

- ``PLANNINGS`` : Dictionnaire des plannings avec leurs propriétés
  correspondantes. Il faut que chaque UV/UE gérées aient un et un seul
  planning correspondant.

- ``CRENEAU_UV`` : Chemin relatif vers le fichier pdf des créneaux des
  UVS ingénieur.

- ``DEFAULT_INSTRUCTOR`` : Intervenant par défaut utilisé dans les
  tâches :class:`~guv.tasks.calendar.CalInst` et
  :class:`~guv.tasks.ical.IcalInst`.

- ``TURN`` : Dictionnaire des jours qui sont changés en d'autres jours
  de la semaine. Il s'agit d'une valeur par défaut qui peut être
  supplantée par planning dans ``PLANNINGS``.

- ``SKIP_DAYS_C`` : Liste des jours (hors samedi/dimanche) où il n'y a
  pas cours. Il s'agit d'une valeur par défaut qui peut être
  supplantée par planning dans ``PLANNINGS``.

- ``SKIP_DAYS_D`` : Liste des jours (hors samedi/dimanche) où il n'y a
  pas TD. Il s'agit d'une valeur par défaut qui peut être supplantée
  par planning dans ``PLANNINGS``.

- ``SKIP_DAYS_T`` : Liste des jours (hors samedi/dimanche) où il n'y a
  pas TP. Il s'agit d'une valeur par défaut qui peut être supplantée
  par planning dans ``PLANNINGS``.

- ``DEBUG`` : Un entier qui règle le niveau de log, par défaut 30.
  Plus l'entier est petit, plus le niveau de log est important.

- ``TASKS`` : Liste de chemins vers des fichiers Python définissant
  des tâches, voir :ref:`creation-tache`.

Liste des variables reconnues dans les fichiers ``config.py`` d'UV
------------------------------------------------------------------

- ``ENT_LISTING`` : Chemin relatif vers le fichier de l'UV tel que
  fourni par l'ENT, voir :ref:`ent-listing`.

- ``AFFECTATION_LISTING`` : Chemin relatif vers le fichier des
  créneaux de Cours/TD/TP, voir :ref:`affectation`.

- ``MOODLE_LISTING`` : Chemin relatif vers le fichier Moodle qu'on
  peut télécharger en allant dans ``Configuration du carnet de notes``
  et en sélectionnant ``Feuille de calcul Excel`` dans le menu
  déroulant et ensuite ``Télécharger``, voir :ref:`moodle-listing`.

- ``DOCS`` : Variable sur laquelle appeler des méthodes pour agréger
  d'autres documents en plus des documents usuels, voir
  :ref:`incorporation`.
