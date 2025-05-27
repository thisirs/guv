Modifies the central file using a function.

``func`` is a function that takes a *DataFrame* representing the central file
and returns the modified *DataFrame*.

A ``msg`` can be provided to describe what the function does. It will be
displayed when the aggregation is performed. Otherwise, a generic message
will be shown.

Parameters
----------

func : :obj:`callable`
    Function that takes a *DataFrame* and returns a modified *DataFrame*.

msg : :obj:`str`, optional
    A message describing the operation.

Examples
--------

- Add a student missing from the official listing:

  .. code:: python

     import pandas as pd

     df_one = (
         pd.DataFrame(
             {
                 "Last name": ["NICHOLS"],
                 "Name": ["Juliette"],
                 "Email": ["juliette.nichols@silo18.fr"],
             }
         ),
     )

     DOCS.apply_df(lambda df: pd.concat((df, df_one)))

- Remove duplicate students:

  .. code:: python

     DOCS.apply_df(
         lambda df: df.loc[~df["Email"].duplicated(), :],
         msg="Remove duplicate students"
     )
