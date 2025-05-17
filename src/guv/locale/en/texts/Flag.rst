Flag a list of students in a new column

The document to aggregate is a list of student names displayed
line by line.

Parameters
----------

filename_or_string : :obj:`str`
    Path to the file to aggregate, or the file content as a string.

colname : :obj:`str`
    Name of the column in which to place the flag.

flags : :obj:`str`, optional
    The two flag values used, default is "Yes" and empty.

Examples
--------

Aggregating a file with student names as header:

The file "tiers_temps.txt":

.. code:: text

   # Comments
   Bob Morane

   # Robust to circular permutation and case
   aRcTor BoB

The aggregation instruction:

.. code:: python

   DOCS.flag("documents/tiers_temps.txt", colname="Tiers-temps")
