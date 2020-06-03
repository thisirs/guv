import sys

from doit.cmd_base import ModuleTaskLoader
from doit.doit_cmd import DoitMain
from doit import loader

from .utils_noconfig import ParseArgAction
from .config import settings

# Make doit config accessible for doit
DOIT_CONFIG = settings.DOIT_CONFIG


from .dodo_instructors import *
from .dodo_utc import *
from .dodo_grades import *
from .dodo_students import *
from .dodo_trombinoscope import *
from .dodo_moodle import *
from .dodo_ical import *
from .dodo_calendar import *
from .dodo_attendance import *


def main():
    if len(sys.argv) == 1:
        # No command-line arguments, run doit normally
        sys.exit(DoitMain(ModuleTaskLoader(globals())).run([]))
    elif len(sys.argv) >= 2:
        arg = sys.argv[1]
        if arg == 'doit':
            # If first argument is doit, delete it and pass the rest
            # to doit
            del sys.argv[1]
            sys.exit(DoitMain(ModuleTaskLoader(globals())).run(sys.argv[1:]))
        elif arg in [
                "auto",
                "clean",
                "dumpdb",
                "forget",
                "ignore",
                "info",
                "list",
                "reset-dep",
                "run",
                "strace",
                "help"]:
            # If non-task command, run it without modifying command
            # line arguments
            sys.exit(DoitMain(ModuleTaskLoader(globals())).run(sys.argv[1:]))
        elif arg == "tabcompletion":
            # Handle tabcompletion argument specially
            mtl = ModuleTaskLoader(globals())
            tasks = loader.load_tasks(mtl.namespace)
            actions = [task.actions for task in tasks]
            actions = [task.actions[0] for task in tasks if task.actions]
            parser_actions = [e for e in actions if type(e) == ParseArgAction]
            parsers = [p.parser for p in parser_actions]
        else:
            # Run doit without command-line arguments to avoid errors.
            # Doit tasks can handle sys.argv itself
            sys.exit(DoitMain(ModuleTaskLoader(globals())).run(sys.argv[1:2]))
