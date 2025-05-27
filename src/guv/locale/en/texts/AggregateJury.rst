Aggregates the result of a jury from the task :class:`~guv.tasks.gradebook.XlsGradeBookJury`.

The equivalent using :func:`~guv.helpers.Documents.aggregate` is written as:

.. code:: python

   DOCS.aggregate(
       "generated/jury_gradebook.xlsx",
       on="Email",
       subset=["Aggregated grade", "ECTS grade"]
   )

Parameters
----------

filename : :obj:`str`
    The path to the file to aggregate.

Examples
--------

.. code:: python

   DOCS.aggregate_jury("generated/jury_gradebook.xlsx")
