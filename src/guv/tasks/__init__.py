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
                     YamlQCM, CsvAmcList)
from .ical import IcalInst, IcalUv
from .instructors import WeekSlotsDetails, XlsInstructors, XlsRemplacements
from .moodle import (
    CsvCreateGroups,
    CsvGroups,
    CsvGroupsGroupings,
    FetchGroupId,
    HtmlInst,
    HtmlTable,
    JsonGroup,
    JsonRestriction,
)
from .students import (
    CsvInscrits,
    XlsStudentData,
    XlsStudentDataMerge,
    ZoomBreakoutRooms,
    MaggleTeams,
    SendEmail,
)
from .trombinoscope import PdfTrombinoscope
from .utc import (
    XlsUTP,
    Planning,
    PlanningSlots,
    PlanningSlotsAll,
    UtcUvListToCsv,
    WeekSlots,
    WeekSlotsAll,
)
