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
