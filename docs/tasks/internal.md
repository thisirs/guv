# Tâches intermédiaires

Les tâches suivantes sont des tâches internes qu'on a normalement pas
besoin d'exécuter car elles sont des dépendances des tâches usuelles.

```{eval-rst}
.. automodule:: guv.tasks.internal
   :exclude-members:
```

```{eval-rst}
.. autoclass:: guv.tasks.internal.Planning
   :exclude-members:

   Cette tâche ne dépend d'aucune autre classe.

   Cette tâche est une dépendance pour les tâches suivantes :

   - :class:`guv.tasks.ical.IcalSlots`
   - :class:`guv.tasks.internal.PlanningSlots`
```

```{eval-rst}
.. autoclass:: guv.tasks.internal.PlanningSlots
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.internal.Planning`
   - :class:`guv.tasks.internal.WeekSlots`

   Cette tâche est une dépendance pour les tâches suivantes :

   - :class:`guv.tasks.moodle.HtmlTable`
   - :class:`guv.tasks.ical.IcalUv`
   - :class:`guv.tasks.moodle.JsonRestriction`
   - :class:`guv.tasks.internal.PlanningSlotsAll`
   - :class:`guv.tasks.instructors.XlsRemplacements`
```

```{eval-rst}
.. autoclass:: guv.tasks.internal.PlanningSlotsAll
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.internal.PlanningSlots`

   Cette tâche est une dépendance pour les tâches suivantes :

   - :class:`guv.tasks.ical.IcalInst`
```

```{eval-rst}
.. autoclass:: guv.tasks.internal.UtcUvListToCsv
   :exclude-members:

   Cette tâche ne dépend d'aucune autre classe.

   Cette tâche est une dépendance pour les tâches suivantes :

   - :class:`guv.tasks.internal.WeekSlots`
```

```{eval-rst}
.. autoclass:: guv.tasks.internal.WeekSlots
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.internal.UtcUvListToCsv`

   Cette tâche est une dépendance pour les tâches suivantes :

   - :class:`guv.tasks.calendar.CalUv`
   - :class:`guv.tasks.internal.PlanningSlots`
   - :class:`guv.tasks.internal.WeekSlotsAll`
   - :class:`guv.tasks.instructors.WeekSlotsDetails`
```

```{eval-rst}
.. autoclass:: guv.tasks.internal.WeekSlotsAll
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.internal.WeekSlots`

   Cette tâche est une dépendance pour les tâches suivantes :

   - :class:`guv.tasks.calendar.CalInst`
```

```{eval-rst}
.. autoclass:: guv.tasks.internal.XlsStudentData
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.internal.XlsStudentData`

   Cette tâche est une dépendance pour les tâches suivantes :

   - :class:`guv.tasks.grades.CsvAmcList`
   - :class:`guv.tasks.moodle.CsvCreateGroups`
   - :class:`guv.tasks.grades.CsvForUpload`
   - :class:`guv.tasks.moodle.CsvGroups`
   - :class:`guv.tasks.moodle.JsonGroup`
   - :class:`guv.tasks.students.MaggleTeams`
   - :class:`guv.tasks.students.PasswordFile`
   - :class:`guv.tasks.attendance.PdfAttendance`
   - :class:`guv.tasks.attendance.PdfAttendanceFull`
   - :class:`guv.tasks.trombinoscope.PdfTrombinoscope`
   - :class:`guv.tasks.students.SendEmail`
   - :class:`guv.tasks.gradebook.XlsGradeBookGroup`
   - :class:`guv.tasks.gradebook.XlsGradeBookJury`
   - :class:`guv.tasks.gradebook.XlsGradeBookNoGroup`
   - :class:`guv.tasks.grades.YamlQCM`
   - :class:`guv.tasks.students.ZoomBreakoutRooms`
```
