Excel file for individual grading

This task generates an Excel file to easily input individual grades using one or
more detailed marking schemes.

The Excel file can also be split into multiple worksheets based on a column in
the ``effectif.xlsx`` file using the ``--worksheets`` argument. Within each
worksheet, students can be ordered using the ``--order-by`` argument. Additional
columns can be included in the first sheet using the ``--extra-cols`` argument.
The path(s) to one or more detailed marking schemes can be provided via the
``--marking-scheme`` argument. If this argument is not provided, the marking
scheme(s) will be requested interactively.

The marking scheme file must be in YAML format. The structure of the assignment
is specified hierarchically, with final-level lists containing the number of
points assigned to each question, optionally followed by a scale (default
is 1), and optional details (not shown in the Excel file).

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
         - scale: 3
       Question 3:
         - points: 2
         - details: |
             Difficult question, don't grade too harshly.
     Part 2:
       Question 1:
         - points: 2
       Question 2:
         - points: 2

Final grades can then be easily merged into the central file by configuring the
``DOCS`` variable.

{options}

Examples
--------

- Grade file with a marking scheme defined interactively, on a single Excel
  sheet:

  .. code:: bash

     guv xls_grade_book_no_group --name Exam1

- Grade file for an assignment using a provided marking scheme, split by
  tutorial groups:

  .. code:: bash

     guv xls_grade_book_no_group \
       --name Exam1 \
       --marking-scheme documents/marking_scheme_exam1.yml \
       --worksheets "tutorial_groups"

  with the YAML file containing, for example:

  .. code:: yaml

     Exercise 1:
       Question 1:
         - points: 1
     Exercise 2:
       Question 1:
         - points: 1

- Grade file for an individual oral exam, split by exam day (column ``Exam day``
  in ``effectif.xlsx``), and ordered by speaking order (column ``Speaking
  order`` in ``effectif.xlsx``):

  .. code:: bash

     guv xls_grade_book_no_group \
       --name OralExam1 \
       --marking-scheme documents/marking_scheme.yml \
       --worksheets "Exam day" \
       --order-by "Speaking order"

  with the YAML file containing, for example:

  .. code:: yaml

     Content:
     Form:
