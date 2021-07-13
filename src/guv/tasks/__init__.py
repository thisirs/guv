"""Ce module rassemble toutes les tâches disponibles dans **guv**.
Pour les exécuter, il faut utiliser la version *snake-case* du nom de
la classe. Par exemple

.. code:: bash

   guv pdf_attendance --title "Examen de TP" --group TP

"""

from .utc import (
    UtcUvListToCsv,
    CsvAllCourses,
)

from .ical import (
    IcalInst,
)

from .trombinoscope import (
    PdfTrombinoscope,
)

from .attendance import (
    PdfAttendance,
    PdfAttendanceFull,
)

from .calendar import (
    CalUv,
    CalInst,
)

from .students import (
    CsvInscrits,
    XlsStudentData,
    XlsStudentDataMerge,
    CsvExamGroups,
    CsvMoodleGroups,
    CsvGroupsGroupings,
    ZoomBreakoutRooms,
)

from .grades import (
    CsvForUpload,
    XlsMergeFinalGrade,
    XlsGradeSheet,
    YamlQCM,
    XlsAssignmentGrade,
)

from .instructors import (
    XlsInstructors,
    AddInstructors,
    XlsInstDetails,
    XlsUTP,
    XlsAffectation,
)

from .moodle import (
    CsvGroups,
    HtmlInst,
    HtmlTable,
    JsonRestriction,
    JsonGroup,
    CsvCreateGroups,
    FetchGroupId,
)
