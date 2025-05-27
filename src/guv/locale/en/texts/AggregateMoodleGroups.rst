Aggregates group data from the "Group Choice" activity.

Since the group column is always named "Groupe", the ``colname`` argument
allows you to specify a different name. If the column already exists in
the central file, it can be backed up using the ``backup`` option.

Parameters
----------

filename : :obj:`str`
    The path to the file to aggregate.

colname: :obj:`str`
    The column name to store group information in.

backup : :obj:`bool`
    Save the column before making any changes

Examples
--------

.. code:: python

   DOCS.aggregate_moodle_groups("documents/Paper study groups.xlsx", "Paper")
