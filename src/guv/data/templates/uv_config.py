"""UV (course unit) configuration file"""

# Debug mode
# DEBUG = "INFO"

from guv.helpers import Documents

DOCS = Documents()

# Relative path to the listing from Moodle
# DOCS.add_moodle_listing("...")

# Course group change file
# This file handles changes in course groups.
# Each line indicates a change in the form:
# id1 --- id2
# The identifiers can be email addresses or full names
# DOCS.switch("...", colname="Cours")

# Tutorial (TD) group change file
# This file handles changes in TD groups.
# Each line indicates a change in the form:
# id1 --- id2
# The identifiers can be email addresses or full names
# DOCS.switch("...", colname="TD")

# Lab (TP) group change file
# This file handles changes in TP groups.
# Each line indicates a change in the form:
# id1 --- id2
# The identifiers can be email addresses or full names
# DOCS.switch("...", colname="TP")

# Mapping between the names of the Cours/TD/TP groups and their Moodle identifiers
MOODLE_GROUPS = None
