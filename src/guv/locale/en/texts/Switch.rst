Performs value swaps in a column

The ``colname`` argument specifies the column in which to perform
the swaps. If the ``backup`` argument is provided, the column is
saved before any modification (with a ``_orig`` suffix). If the
``new_colname`` argument is provided, the column is copied to a new
column named ``new_colname`` and the modifications are applied to
this new column.

Parameters
----------

filename_or_string : :obj:`str`
    Path to the file to aggregate, or the content of the file as a string.
colname : :obj:`str`
    Name of the column where the changes will be applied
backup : :obj:`bool`
    Save the column before making any changes
new_colname : :obj:`str`
    Name of the new column

Examples
--------

.. code:: python

   DOCS.switch("fichier_échange_TP", colname="TP")

.. code:: python

   DOCS.switch("Dupont --- Dupond", colname="TP")
