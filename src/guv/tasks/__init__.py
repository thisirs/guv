"""Ce module rassemble toutes les tâches disponibles dans **guv**.
Pour les exécuter, il faut utiliser la version *snake-case* du nom de
la classe. Par exemple

.. code:: bash

   guv pdf_attendance --title "Examen de TP" --group TP

"""

from .attendance import PdfAttendance, PdfAttendanceFull
from .calendar import CalInst, CalUv
from .gradebook import XlsGradeBookGroup, XlsGradeBookJury, XlsGradeBookNoGroup
from .grades import CsvAmcList, CsvForUpload, YamlQCM
from .ical import IcalInst, IcalSlots, IcalUv
from .instructors import (WeekSlotsDetails, XlsInstructors, XlsRemplacements,
                          XlsUTP)
from .internal import (Planning, PlanningSlots, PlanningSlotsAll,
                       UtcUvListToCsv, WeekSlots, WeekSlotsAll, XlsStudentData)
from .moodle import (CsvCreateGroups, CsvGroups, CsvGroupsGroupings,
                     FetchGroupId, HtmlInst, HtmlTable, JsonGroup,
                     JsonRestriction)
from .students import MaggleTeams, PasswordFile, SendEmail, ZoomBreakoutRooms
from .trombinoscope import PdfTrombinoscope
