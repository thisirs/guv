# Intervenants

```{eval-rst}
.. automodule:: guv.tasks.instructors
   :exclude-members:
```

```{eval-rst}
.. autoclass:: guv.tasks.instructors.WeekSlotsDetails
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.internal.WeekSlots`
   - :class:`guv.tasks.instructors.XlsInstructors`

   Cette tâche est une dépendance pour les tâches suivantes :

   - :class:`guv.tasks.moodle.HtmlInst`
   - :class:`guv.tasks.instructors.XlsRemplacements`
```

```{eval-rst}
.. autoclass:: guv.tasks.instructors.XlsInstructors
   :exclude-members:

   Cette tâche ne dépend d'aucune autre classe.

   Cette tâche est une dépendance pour les tâches suivantes :

   - :class:`guv.tasks.instructors.WeekSlotsDetails`
```

```{eval-rst}
.. autoclass:: guv.tasks.instructors.XlsRemplacements
   :exclude-members:

   Cette tâche dépend de :

   - :class:`guv.tasks.internal.PlanningSlots`
   - :class:`guv.tasks.instructors.WeekSlotsDetails`

   Aucune tâche ne dépend de celle-ci.
```

```{eval-rst}
.. autoclass:: guv.tasks.instructors.XlsUTP
   :exclude-members:

   Cette tâche ne dépend d'aucune autre classe.

   Aucune tâche ne dépend de celle-ci.
```
