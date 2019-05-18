import os
import sys

from doit.cmd_base import ModuleTaskLoader
from doit.doit_cmd import DoitMain

# Set configuration files to load
os.environ.setdefault(
    "SETTINGS_FILES",
    ",".join([os.path.abspath("../config.py"), os.path.abspath("./config.py")]),
)

from .config import settings

DOIT_CONFIG = settings.DOIT_CONFIG


from .dodo_instructors import *
from .dodo_utc import *
from .dodo_grades import *
from .dodo_students import *


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "doit":
        del sys.argv[1]
        sys.exit(DoitMain(ModuleTaskLoader(globals())).run(sys.argv[1:]))
    else:
        sys.exit(DoitMain(ModuleTaskLoader(globals())).run(sys.argv[1:2]))
