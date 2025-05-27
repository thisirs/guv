Regex replacements in a column

Replaces, in the ``colname`` column, all occurrences matching the regular
expressions specified in ``reps``.

If the ``backup`` argument is provided, the column is saved before any
modification (with a ``_orig`` suffix). If the ``new_colname`` argument is
provided, the column is copied to a new column named ``new_colname`` and the
modifications are applied to that new column.

A ``msg`` message can be specified to describe what the function does; it will
be displayed when the aggregation is performed. Otherwise, a generic message
will be shown.

Parameters
----------

colname : :obj:`str`
    Name of the column in which to perform replacements
*reps : any number of :obj:`tuple`
    Pairs of regex / replacement
new_colname : :obj:`str`
    Name of the new column
backup : :obj:`bool`
    Save the column before making any changes
msg : :obj:`str`, optional
    A message describing the operation

Examples
--------

.. code:: python

   DOCS.replace_regex("group", (r"group([0-9])", r"G\1"), (r"g([0-9])", r"G\1"))
