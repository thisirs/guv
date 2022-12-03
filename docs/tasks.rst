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

   - :class:`guv.tasks.utc.PlanningSlotsAll`

.. autoclass:: guv.tasks.ical.IcalUv
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.utc.PlanningSlots`

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

   - :class:`guv.tasks.utc.WeekSlots`

.. autoclass:: guv.tasks.calendar.CalInst
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.utc.WeekSlotsAll`

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

   - :class:`guv.tasks.utc.WeekSlots`
   - :class:`guv.tasks.students.XlsStudentDataMerge`

Intervenants
------------

.. automodule:: guv.tasks.instructors
   :exclude-members:

.. autoclass:: guv.tasks.instructors.XlsRemplacements
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.utc.PlanningSlots`
   - :class:`guv.tasks.instructors.WeekSlotsDetails`

.. autoclass:: guv.tasks.utc.XlsUTP
   :exclude-members:

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

   - :class:`guv.tasks.instructors.WeekSlotsDetails`

.. autoclass:: guv.tasks.moodle.HtmlTable
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.utc.PlanningSlots`

.. autoclass:: guv.tasks.moodle.JsonRestriction
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.utc.PlanningSlots`

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

   - :class:`guv.tasks.utc.WeekSlots`

.. autoclass:: guv.tasks.utc.PlanningSlots
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.utc.WeekSlots`

   Cette tâche est une dépendance pour les tâches suivantes :

   - :class:`guv.tasks.instructors.XlsRemplacements`
   - :class:`guv.tasks.utc.PlanningSlotsAll`
   - :class:`guv.tasks.moodle.HtmlTable`
   - :class:`guv.tasks.moodle.JsonRestriction`
   - :class:`guv.tasks.ical.IcalUv`

.. autoclass:: guv.tasks.utc.PlanningSlotsAll
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.utc.PlanningSlots`

   Cette tâche est une dépendance pour les tâches suivantes :

   - :class:`guv.tasks.ical.IcalInst`

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
   - :class:`guv.tasks.gradebook.XlsGradeBookJury`
   - :class:`guv.tasks.gradebook.XlsGradeBookGroup`
   - :class:`guv.tasks.gradebook.XlsGradeBookNoGroup`
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

   - :class:`guv.tasks.instructors.WeekSlotsDetails`

.. autoclass:: guv.tasks.utc.WeekSlotsAll
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.utc.WeekSlots`

   Cette tâche est une dépendance pour les tâches suivantes :

   - :class:`guv.tasks.ical.IcalInst`

.. autoclass:: guv.tasks.instructors.WeekSlotsDetails
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.utc.WeekSlots`
   - :class:`guv.tasks.instructors.XlsInstructors`

   Cette tâche est une dépendance pour les tâches suivantes :

   - :class:`guv.tasks.instructors.XlsRemplacements`

.. autoclass:: guv.tasks.utc.WeekSlots
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.utc.UtcUvListToCsv`

   Cette tâche est une dépendance pour les tâches suivantes :

   - :class:`guv.tasks.utc.PlanningSlots`
   - :class:`guv.tasks.utc.WeekSlotsAll`
   - :class:`guv.tasks.calendar.CalUv`
   - :class:`guv.tasks.moodle.HtmlInst`
   - :class:`guv.tasks.instructors.WeekSlotsDetails`
   - :class:`guv.tasks.grades.XlsAssignmentGrade`
