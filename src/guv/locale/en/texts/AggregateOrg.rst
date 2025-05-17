Aggregation of a file in Org format.

The document to aggregate is in Org format. The headings serve as
keys for aggregation, and the content under those headings is aggregated.

Parameters
----------

filename : :obj:`str`
    Path to the Org file to aggregate.

colname : :obj:`str`
    Name of the column in which to store the information
    from the Org file.

on : :obj:`str`, optional
    Column from the ``effectif.xlsx`` file used as the key to
    aggregate with the headings from the Org file. By default,
    the headings must contain the students' first and last names.

postprocessing : :obj:`callable`, optional
    Post-processing to apply to the *DataFrame* after integrating
    the Org file.

Examples
--------

- Aggregating a file where the headings are student names:

  The Org file:

  .. code:: text

     * Bob Morane
       Frequently absent
     * Untel
       See excuse email

  The aggregation command:

  .. code:: python

     DOCS.aggregate_org("documents/infos.org", colname="Information")

- Aggregating a file where the headings match elements from an
  existing column. For example, you can aggregate project grades
  from an Org file, grouped by project team. Specify the column
  containing the project groups, e.g., "Project1_group".

  The Org file:

  .. code:: text

     * Project1_Group1
       A
     * Project1_Group2
       B

  The aggregation command:

  .. code:: python

     DOCS.aggregate_org("documents/infos.org", colname="Project 1 Grade", on="Project1_group")
