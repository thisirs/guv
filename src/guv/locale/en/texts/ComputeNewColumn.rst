Creating a column from other columns

The columns required for the calculation are specified in ``cols``.
In case you want to change the column used for the calculation
without modifying the ``func`` function, you can provide a
tuple ``("col", "other_col")`` where ``col`` is the name used in
``func`` and ``other_col`` is the actual column used.

The ``func`` function that computes the new column receives a Pandas
*Series* of all the values from the specified columns.

Parameters
----------

*cols : list of :obj:`str`
    List of columns provided to the ``func`` function
func : :obj:`callable`
    Function that takes a dictionary of "column names/values"
    as input and returns a computed value
colname : :obj:`str`
    Name of the column to create
msg : :obj:`str`, optional
    A message describing the operation

Examples
--------

- Weighted average of two grades:

  .. code:: python

     def average(grades):
         return .4 * grades["Note_médian"] + .6 * grades["Note_final"]

     DOCS.compute_new_column("Note_médian", "Note_final", func=average, colname="Note_moyenne")

- Average ignoring undefined values:

  .. code:: python

     def average(grades):
         return grades.mean()

     DOCS.compute_new_column("note1", "note2", "note3", func=average, colname="Note_moyenne")

- Recalculation with a modified grade without redefining the ``average`` function:

  .. code:: python

     DOCS.compute_new_column(
         ("note1", "note1_fix"), "note2", "note3", func=average, colname="Note_moyenne (fix)"
     )
