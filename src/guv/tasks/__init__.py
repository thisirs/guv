"""Ce module rassemble toutes les tâches disponibles dans **guv**.
Pour les exécuter, il faut utiliser la version *snake-case* du nom de
la classe. Par exemple

.. code:: bash

   guv pdf_attendance --title "Examen de TP" --group TP

"""

from .attendance import PdfAttendance, PdfAttendanceFull
from .calendar import CalInst, CalUv
from .gradebook import XlsGradeBookGroup, XlsGradeBookJury, XlsGradeBookNoGroup
from .grades import (CsvForUpload, XlsAssignmentGrade, XlsMergeFinalGrade,
                     YamlQCM)
from .ical import IcalInst
from .instructors import (AddInstructors, XlsAffectation, XlsInstDetails,
                          XlsInstructors, XlsUTP)
from .moodle import (CsvCreateGroups, CsvGroups, CsvGroupsGroupings,
                     FetchGroupId, HtmlInst, HtmlTable, JsonGroup,
                     JsonRestriction)
from .students import (CsvExamGroups, CsvInscrits, CsvMoodleGroups,
                       XlsStudentData, XlsStudentDataMerge, ZoomBreakoutRooms)
from .trombinoscope import PdfTrombinoscope
from .utc import CsvAllCourses, UtcUvListToCsv, UTP
