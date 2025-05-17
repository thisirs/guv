Random creation of student groups

This task creates a CSV file assigning students to groups, ready to be uploaded to Moodle.
If the ``--grouping`` option is provided, groups are created within each subgroup.

The number of groups created (globally or per subgroup depending on ``--grouping``) is controlled by one of the mutually exclusive options:  
``--proportions``, ``--group-size``, or ``--num-groups``:

- ``--proportions``: specify the group count via a list of proportions.
- ``--group-size``: specify the maximum size of each group.
- ``--num-groups``: specify the desired number of groups.

Group names are controlled using the ``--template`` option. The following substitutions are available in ``--template``:

- ``{title}``: replaced by the title (first argument)
- ``{grouping_name}``: replaced by the subgroup name (if ``--grouping`` is used)
- ``{group_name}``: name of the current group (if ``--names`` is used)
- ``#``: sequential group number (used if ``--names`` is not specified)
- ``@``: sequential group letter (used if ``--names`` is not specified)

The ``--names`` option may be a list of names to use or a file containing names line by line.  
These are selected randomly if the ``--random`` flag is set.

The ``--global`` flag prevents the group name generation from resetting when switching subgroup (useful with ``--grouping``).

By default, the student list is shuffled before creating contiguous groups.  
Use ``--ordered`` to create groups alphabetically. You may also provide a list of columns for sorting.

Group creation constraints:

- ``--other-groups``: names of existing group columns to avoid re-forming
- ``--affinity-groups``: names of group columns to try to preserve

{options}

Examples
--------

- Create groups of 3 within each TD subgroup:

  .. code:: bash

     guv csv_create_groups Project1 -G TD --group-size 3

- Create new trios in each TD subgroup, avoiding those already grouped in ``Project1``:

  .. code:: bash

     guv csv_create_groups Project2 -G TD --group-size 3 --other-groups Project1

- Split each TD subgroup in half using group names like D1i, D1ii, D2i, D2ii:

  .. code:: bash

     guv csv_create_groups HalfGroup -G TD --proportions .5 .5 --template '{grouping_name}{group_name}' --names i ii

- Divide the class into two parts alphabetically with group names ``First`` and ``Second``:

  .. code:: bash

     guv csv_create_groups Half --proportions .5 .5 --ordered --names First Second --template '{group_name}'

.. rubric:: Notes

To be Moodle-compatible, the generated file does not include a column header.  
To merge this group file with the main dataset, use the ``kw_read`` argument as follows:

.. code:: python

   DOCS.aggregate(
       "generated/Project1_groups.csv",
       on="Email",
       kw_read={"header": None, "names": ["Email", "Group"]},
   )
