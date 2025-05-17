Excel grade file by group

This task generates an Excel file for grading by groups, avoiding the need to
copy the same grade for each member of a group. Student groups are specified
using the ``--group-by`` argument. One or more detailed marking schemes can be
provided with the ``--marking-scheme`` argument.

The Excel file can also be split into multiple worksheets based on a column from
the ``effectif.xlsx`` file, using the ``--worksheets`` argument. Within each
group, students can be ordered according to the ``--order-by`` argument.

You can add extra columns to the first worksheet using the ``--extra-cols``
argument.

The path(s) to a detailed marking scheme file can be specified via
``--marking-scheme``. If this argument is not used, the marking schemes will be
requested interactively. The marking scheme file must be in YAML format.

The assignment structure is defined hierarchically, ending with a list of
questions specifying the number of points awarded and optionally a coefficient
(default is 1) and details (not included in the Excel file).

For example:

.. code:: yaml

   Exercise 1:
     Question 1:
       - points: 1
   Problem:
     Part 1:
       Question 1:
         - points: 2
       Question 2:
         - points: 2
         - coeff: 3
       Question 3:
         - points: 2
         - details: |
             Difficult question, don't grade too harshly.
     Part 2:
       Question 1:
         - points: 2
       Question 2:
         - points: 2

Final grades can then be easily merged into the central file using the ``DOCS``
variable.

{options}

Examples
--------

Grade file by project group:

.. code:: bash

   guv xls_grade_book_group \
     --name Devoir1 \
     --marking-scheme documents/barème_devoir1.yml \
     --group-by 'Groupe Project'

With the YAML file containing, for example:

.. code:: yaml

   Exercise 1:
     Question 1:
       - points: 1
   Exercise 2:
     Question 1:
       - points: 1
