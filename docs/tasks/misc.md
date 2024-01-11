# Tâches intermédiaires

Les tâches suivantes sont des tâches internes qu'on a normalement pas
besoin d'exécuter car elles sont des dépendances des tâches usuelles.

```{eval-rst}
.. autoclass:: guv.tasks.utc.UtcUvListToCsv
   :exclude-members:

   Cette tâche est une dépendance pour les tâches suivantes :

   - :class:`guv.tasks.utc.WeekSlots`
```

```{eval-rst}
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
```

```{eval-rst}
.. autoclass:: guv.tasks.utc.PlanningSlotsAll
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.utc.PlanningSlots`

   Cette tâche est une dépendance pour les tâches suivantes :

   - :class:`guv.tasks.ical.IcalInst`
```

```{eval-rst}
.. autoclass:: guv.tasks.students.CsvInscrits
   :exclude-members:

   Cette tâche est une dépendance pour les tâches suivantes :

   - :class:`guv.tasks.students.XlsStudentData`
```

```{eval-rst}
.. autoclass:: guv.tasks.students.XlsStudentData
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.students.CsvInscrits`

   Cette tâche est une dépendance pour les tâches suivantes :

   - :class:`guv.tasks.students.XlsStudentDataMerge`
```

```{eval-rst}
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
   - :class:`guv.tasks.students.SendEmail`
   - :class:`guv.tasks.students.ZoomBreakoutRooms`
   - :class:`guv.tasks.trombinoscope.PdfTrombinoscope`
```

```{eval-rst}
.. autoclass:: guv.tasks.instructors.XlsInstructors
   :exclude-members:

   Cette tâche est une dépendance pour les tâches suivantes :

   - :class:`guv.tasks.instructors.WeekSlotsDetails`
```

```{eval-rst}
.. autoclass:: guv.tasks.utc.WeekSlotsAll
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.utc.WeekSlots`

   Cette tâche est une dépendance pour les tâches suivantes :

   - :class:`guv.tasks.ical.IcalInst`
```

```{eval-rst}
.. autoclass:: guv.tasks.instructors.WeekSlotsDetails
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.utc.WeekSlots`
   - :class:`guv.tasks.instructors.XlsInstructors`

   Cette tâche est une dépendance pour les tâches suivantes :

   - :class:`guv.tasks.instructors.XlsRemplacements`
```

```{eval-rst}
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
```
