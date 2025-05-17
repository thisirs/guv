Replaces the value of a cell.

``name_or_email`` is the student's full name or email address, and ``colname``
is the name of the column where the change should be made. The new value is
provided via ``value``.

Parameters
----------

name_or_email : :obj:`str`
    The student's full name or email address.

colname : :obj:`str`
    The name of the column where the modification should be made.

value :
    The value to assign.

msg : :obj:`str`
    A message describing the operation.

Examples
--------

.. code:: python

   DOCS.apply_cell("Mark Watney", "DIY Grade", 20)
