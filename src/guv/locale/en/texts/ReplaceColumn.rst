Replacements in a column

Replaces values specified in ``rep_dict`` in the column
``colname``.

If the ``backup`` argument is provided, the column is saved
before any modification (with a ``_orig`` suffix). If
the ``new_colname`` argument is provided, the column is copied
to a new column named ``new_colname`` and changes are made on
this new column.

A message ``msg`` can be specified to describe what the function
does; it will be displayed when the aggregation is performed.
Otherwise, a generic message will be shown.

Parameters
----------

colname : :obj:`str`
    Name of the column in which to perform replacements
rep_dict : :obj:`dict`
    Dictionary of replacements
new_colname : :obj:`str`
    Name of the new column
backup : :obj:`bool`
    Save the column before making any changes
msg : :obj:`str`
    A message describing the operation

Examples
--------

.. code:: python

   DOCS.replace_column("group", {"TD 1": "TD1", "TD 2": "TD2"})

.. code:: python

   ECTS_TO_NUM = {
       "A": 5,
       "B": 4,
       "C": 3,
       "D": 2,
       "E": 1,
       "F": 0
   }
   DOCS.replace_column("Note_TP", ECTS_TO_NUM, backup=True)
