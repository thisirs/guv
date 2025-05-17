"""UV (course unit) configuration file"""

# Debug mode
# DEBUG = "INFO"

from guv.helpers import Documents

DOCS = Documents()

# Relative path to the listing from Moodle
# DOCS.add_moodle_listing("...")

# Lecture group change file
# This file handles changes in lecture groups.
# Each line indicates a change in the form:
# id1 --- id2
# The identifiers can be email addresses or full names
# DOCS.switch("...", colname="Lecture")

# Tutorial group change file.
# This file handles changes in tutorials groups. Each
# line indicates a change in the form:
# id1 --- id2
# The identifiers can be email addresses or full names
# DOCS.switch("...", colname="Tutorial")

# Practical work group change.
# file This file handles changes in practical work
# groups. Each line indicates a change in the form:
# id1 --- id2
# The identifiers can be email addresses or full names
# DOCS.switch("...", colname="Practical work")

# Mapping between the names of the Lecture/Tutorial/Practical work groups and
# their Moodle identifiers
MOODLE_GROUPS = None
