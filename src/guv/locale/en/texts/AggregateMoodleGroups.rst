Aggregates group data from the "Group Choice" activity.

Since the group column is always named "Groupe", the ``colname`` argument
allows you to specify a different name. If the column already exists in
the central file, it can be backed up using the ``backup`` option.

Examples
--------

.. code:: python

   DOCS.aggregate_moodle_groups("documents/Paper study groups.xlsx", "Paper")
