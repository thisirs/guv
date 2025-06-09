Excel file for managing a UV jury

This task generates an Excel file for managing a UV/UE jury. The optional
``--name`` argument allows you to specify a name for the file (default is
``jury``).

The optional ``--config`` argument allows you to provide a configuration file
with the data needed for the jury. If not provided, the configuration will be
requested interactively.

More specifically, the created workbook contains two sheets. The first sheet
includes:

- the name, last name and email columns as specified in ``config.py`` from the
  central ``effectif.xlsx`` file,
- the grades specified in the configuration file (via ``--config`` or
  interactively) that contribute to the final grade,
- a special column named "Aggregated Grade" containing a grade out of 20, with a
  default formula using the weights and maximum scores from the configuration,
- an automatically calculated ECTS grade (A–F) representing the aggregated grade
  based on percentiles,
- other useful columns for the jury that are not grades.

The second sheet provides admission thresholds for each grade, the coefficients
of each grade, the maximum scores, the thresholds used to convert the aggregated
grade to an ECTS grade, and some statistics on grade distribution.

The configuration file must be in YAML format. The grades to be included are
listed under the ``grades`` section. For each grade, you must specify a column
``name`` and optionally:

- a ``passing grade`` (default: -1),
- a ``coefficient`` (default: 1),
- a ``maximum grade`` (default: 20),

Columns that are not grades can be listed under ``others``. For example:

.. code:: yaml

   grades:
     - name: grade1
       passing grade: 8
       coefficient: 2
     - name: grade2
     - name: grade3
   others:
     - info

The ECTS grade and aggregated grade can then be easily merged into the central
file using the ``DOCS`` variable:

.. code:: python

   DOCS.aggregate_jury("generated/jury_gradebook.xlsx")

{options}

Examples
--------

- Grade sheet with the ``quiz``, ``median`` and ``final`` grade (with a
  threshold of 6), and the ``Branche`` info column:

  .. code:: bash

     guv xls_grade_book_jury --config documents/config_jury.yml

  with the YAML file containing, for example:

  .. code:: yaml

     grades:
       - name: quiz
         coefficient: 0.2
         maximum grade: 10
       - name: median
         coefficient: 0.3
       - name: final
         coefficient: 0.5
         passing grade: 6
     others:
       - Branche
