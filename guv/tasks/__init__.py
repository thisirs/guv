from .dodo_utc import (
    UtcUvListToCsv,
    CsvAllCourses,
)

from .dodo_ical import (
    IcalInst,
)

from .dodo_trombinoscope import (
    PdfTrombinoscope,
)

from .dodo_attendance import (
    PdfAttendanceList,
    PdfAttendanceFull,
    AttendanceSheetRoom,
    AttendanceSheet,
)

from .dodo_calendar import (
    CalUv,
    CalInst,
)

from .dodo_students import (
    CsvInscrits,
    XlsStudentData,
    XlsStudentDataMerge,
    CsvExamGroups,
    CsvGroups,
    CsvMoodleGroups,
    CsvGroupsGroupings,
    ZoomBreakoutRooms,
)

from .dodo_grades import (
    CsvForUpload,
    XlsMergeFinalGrade,
    XlsGradeSheet,
    YamlQCM,
    XlsAssignmentGrade,
)

from .dodo_instructors import (
    XlsInstructors,
    AddInstructors,
    XlsInstDetails,
    XlsUTP,
    XlsAffectation,
)

from .dodo_moodle import (
    HtmlInst,
    HtmlTable,
    JsonRestriction,
    JsonGroup,
    CsvCreateGroups,
    FetchGroupId,
)
