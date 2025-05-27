Adds a file to the central file

Simply adds the file if the central file does not yet exist. Otherwise,
uses the function ``func`` to perform the aggregation. The function ``func``
takes as arguments the existing *DataFrame* and the path to the file, and
returns the updated *DataFrame*.

See specialized functions for incorporating standard documents:

- :func:`~guv.helpers.Documents.aggregate`: CSV/Excel document
- :func:`~guv.helpers.Documents.aggregate_org`: Org document

Parameters
----------

filename : :obj:`str`
    The path to the file to aggregate.

func : :obj:`callable`, optional
    A function with signature *DataFrame*, filename: str ->
    *DataFrame* that performs the aggregation.

Examples
--------

- Adding data when there is nothing yet:

  .. code:: python

     DOCS.add("documents/base_listing.xlsx)

- Aggregating using a function:

  .. code:: python

     def function_that_incorporates(df, file_path):
         # Incorporate the file at `file_path` into the DataFrame `df`
         # and return the updated DataFrame.

     DOCS.add("documents/notes.csv", func=function_that_incorporates)

