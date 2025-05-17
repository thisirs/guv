Modifies an existing column using a function.

``colname`` is the name of an existing column, and ``func`` is a function
that takes an element from the column as input and returns a modified value.

A ``msg`` can be provided to describe the operation; it will be displayed
when the aggregation is performed. Otherwise, a generic message will be shown.

Parameters
----------

colname : :obj:`str`
    Name of the column where replacements will be made.

func : :obj:`callable`
    Function that takes an element and returns the modified element.

msg : :obj:`str`
    A message describing the operation.

Examples
--------

.. code:: python

   DOCS.apply("note", lambda e: float(str(e).replace(",", ".")))
