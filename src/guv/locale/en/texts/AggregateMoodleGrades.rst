Aggregates grade sheets exported from Moodle.

The grade sheet must be an export of one or more grades from the
Moodle gradebook in the form of an Excel or CSV file.

Unused columns will be removed. Column renaming can be performed
by specifying ``rename``.

Parameters
----------

filename : :obj:`str`
    The path to the file to aggregate.

rename : :obj:`dict`, optional
    Dictionary to rename columns after incorporation.

Examples
--------

.. code:: python

   DOCS.aggregate_moodle_grades("documents/SY02 Notes.xlsx")
