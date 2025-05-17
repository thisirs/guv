Aggregation of a table from an Excel/CSV file.

The ``left_on`` and ``right_on`` arguments are column names used to perform a join:
``left_on`` is a column in the central file ``effectif.xlsx``, and ``right_on`` is
a column from the file to aggregate. For more complex joins, you can use the
:func:`guv.helpers.id_slug` and :func:`guv.helpers.concat` functions (see Examples).
If ``left_on`` and ``right_on`` have the same value, you can simply specify ``on``.

``subset`` is a list of columns to keep if you don’t want to aggregate all columns.
``drop`` is a list of columns to remove. ``rename`` is a dictionary of columns to rename.
``read_method`` is a *callable* used to read the file and is called with ``kw_read``.
``preprocessing`` and ``postprocessing`` are *callables* that take a *DataFrame* as
input and return a processed one — they are applied before and after the aggregation, respectively.
``merge_policy`` indicates how to handle merging columns with the same name in
``effectif.xlsx`` and the aggregated file.

Parameters
----------

filename : :obj:`str`
    Path to the CSV/Excel file to aggregate.

left_on : :obj:`str`
    Column name in the ``effectif.xlsx`` file used for the join.
    You can also use functions like :func:`guv.helpers.id_slug` and
    :func:`guv.helpers.concat` for multi-column joins.

right_on : :obj:`str`
    Column name in the file to aggregate used for the join.
    Functions like :func:`guv.helpers.id_slug` and :func:`guv.helpers.concat`
    are also supported.

on : :obj:`str`
    Shortcut when ``left_on`` and ``right_on`` are the same.

subset : :obj:`list`, optional
    List of columns to include. By default, all columns are incorporated.

drop : :obj:`list`, optional
    List of columns to exclude from aggregation.

rename : :obj:`dict`, optional
    Dictionary to rename columns after incorporation.

read_method : :obj:`callable`, optional
    Function used to load the file. Pandas functions like ``pd.read_csv`` and
    ``pd.read_excel`` are automatically selected based on file extension
    (".csv", ".xlsx").

kw_read : :obj:`dict`, optional
    Keyword arguments passed to ``read_method``. For example, for a ".csv" file:

    .. code:: python

       kw_read={"header": None, "names": ["Email", "PW group"]}
       kw_read={"na_values": "-"}

preprocessing : :obj:`callable`, optional
    Pre-processing function applied to the *DataFrame* before incorporation.

postprocessing : :obj:`callable`, optional
    Post-processing function applied to the *DataFrame* after incorporation.

merge_policy : :obj:`str`, optional
    Strategy for merging columns with the same name:

    - ``merge``: Merge only if columns complement each other (NA values).
    - ``replace``: Use all non-NA values from the file to aggregate.
    - ``fill_na``: Only replace NA values in ``effectif.xlsx``.
    - ``keep``: Keep the original column from ``effectif.xlsx`` without changes.
    - ``erase``: Overwrite the column with values from the file to aggregate.

Examples
--------

- Aggregating columns from a CSV file, matching the ``email`` column in the CSV
  with ``Email address`` in the central file:

  .. code:: python

     DOCS.aggregate(
         "documents/notes.csv",
         left_on="Email address",
         right_on="email"
     )

- Aggregating only the ``Note`` column:

  .. code:: python

     DOCS.aggregate(
         "documents/notes.csv",
         left_on="Email address",
         right_on="email"
         subset="Note"
     )

- Aggregating and renaming the ``Note`` column to ``Note_médian``:

  .. code:: python

     DOCS.aggregate(
         "documents/notes.csv",
         left_on="Email address",
         right_on="email"
         subset="Note",
         rename={"Note": "Note_médian"}
     )

- Aggregating using a CSV without a header:

  .. code:: python

     DOCS.aggregate(
         "documents/notes.csv",
         on="Email",
         kw_read={"header": None, "names": ["Email", "Grade"]},
     )

- Aggregating based on ``Name`` and ``Last name`` using a slug ID to allow for
  flexible matching (ignores accents, cases, hyphens, etc.):

  .. code:: python

     from guv.helpers import id_slug
     DOCS.aggregate(
         "documents/notes.csv",
         left_on=id_slug("Name", "Last name"),
         right_on=id_slug("Name", "Last name")
     )

- Aggregating when the aggregated file has a single column with both names,
  while the main file separates them:

  .. code:: python

     from guv.helpers import concat
     DOCS.aggregate(
         "documents/notes.csv",
         left_on=concat("Name", "Last name"),
         right_on="Full_name"
     )
