Aggregation of the central file ``effectif.xlsx`` itself.

It is sometimes more convenient to manually add or modify columns directly
in the central file ``effectif.xlsx`` rather than programmatically using
``DOCS.aggregate(...)``, for example. Since *guv* cannot reliably detect
which columns were manually added or modified, you must specify them explicitly
using the ``*columns`` argument.

Parameters
----------

*columns : any number of :obj:`str`
    The manually added or modified columns to retain when updating the
    central file.
