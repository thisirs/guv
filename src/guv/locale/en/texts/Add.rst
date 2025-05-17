Declare an aggregation of a file using a function.

General function to declare the aggregation of a file at path
``filename`` using a function ``func`` which takes as arguments
the existing *DataFrame*, the path to the file, and returns the
updated *DataFrame*.

See specialized functions for incorporating standard documents:

- :func:`~guv.helpers.Documents.aggregate`: CSV/Excel document
- :func:`~guv.helpers.Documents.aggregate_org`: Org document

Parameters
----------

filename : :obj:`str`
    The path to the file to aggregate.

func : :obj:`callable`
    A function with signature *DataFrame*, filename: str ->
    *DataFrame* that performs the aggregation.

Examples
--------

.. code:: python

   def function_that_incorporates(df, file_path):
       # Incorporate the file at `file_path` into the DataFrame `df`
       # and return the updated DataFrame.

   DOCS.add("documents/notes.csv", func=function_that_incorporates)
