Agrège le résultat d'un jury provenant de la tâche
:class:`~guv.tasks.gradebook.XlsGradeBookJury`.

L'équivalent avec :func:`~guv.helpers.Documents.aggregate` s'écrit :

.. code:: python

   DOCS.aggregate(
       "generated/jury_gradebook.xlsx",
       on="Courriel",
       subset=["Note agrégée", "Note ECTS"]
   )

Examples
--------

.. code:: python

   DOCS.aggregate_jury("generated/jury_gradebook.xlsx")

