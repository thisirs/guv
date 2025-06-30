CSV file of groups and groupings for Moodle import

This task generates a CSV file to create groups and groupings directly in Moodle.

You must specify:

- the number of groups per grouping using the ``-g`` option,
- the number of groupings using the ``-G`` option.

The name of the groupings is controlled by a pattern given via ``-F``
(default: ``D##_P1``). The available substitutions are:

- ``##``: replaced by numbers,
- ``@@``: replaced by letters.

The name of the groups is controlled by a pattern given via ``-f``
(default: ``D##_P1_@``). The available substitutions are:

- ``#``: replaced by numbers,
- ``@``: replaced by letters.

{options}

Examples
--------

.. code:: bash

   guv csv_groups_groupings -G 3 -F Grouping_P1 -g 14 -f D##_P1_@
   guv csv_groups_groupings -G 2 -F Grouping_D1 -g 14 -f D1_P##_@
   guv csv_groups_groupings -G 2 -F Grouping_D2 -g 14 -f D2_P##_@
   guv csv_groups_groupings -G 2 -F Grouping_D3 -g 14 -f D3_P##_@
