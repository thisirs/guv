Replaces undefined values in the ``colname`` column

Only one of the options ``na_value`` and ``group_column`` should be
specified. If ``na_value`` is specified, values are unconditionally
replaced with the provided value. If ``group_column`` is specified,
values are filled by grouping on ``group_column`` and using the only
valid value in that column per group.

Parameters
----------

colname : :obj:`str`
    Name of the column where ``NA`` values will be replaced
na_value : :obj:`str`, optional
    Value to replace undefined values with
group_column : :obj:`str`, optional
    Name of the column used for grouping

Examples
--------

- Replace undefined entries in the ``note`` column with
  "ABS":

  .. code:: python

     DOCS.fillna_column("note", na_value="ABS")

- Replace undefined entries within each group identified by the
  ``groupe_projet`` column with the only defined value in that group:

  .. code:: python

     DOCS.fillna_column("note_projet", group_column="groupe_projet")
