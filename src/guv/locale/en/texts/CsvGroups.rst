CSV files of groups from ``effectif.xlsx`` for Moodle

This task generates CSV files containing group assignments based on the data
from ``effectif.xlsx``, suitable for import into Moodle.

The ``--groups`` option allows you to select which group columns to export.
By default, the exported columns are ``Cours``, ``TD``, and ``TP``.

The ``--long`` option enables exporting TD/TP group names in a long format,
i.e., ``TP1``, ``TD1`` instead of ``T1``, ``D1``.

The ``--single`` option allows generating a single combined file.

{options}

Examples
--------

.. code:: bash

   guv csv_groups --groups Groupe_Project
