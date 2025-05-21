"""Ce module rassemble toutes les tâches disponibles dans **guv**.
Pour les exécuter, il faut utiliser la version *snake-case* du nom de
la classe. Par exemple

.. code:: bash

   guv pdf_attendance --title "Examen de TP" --group TP

"""

from .attendance import PdfAttendance, PdfAttendanceFull
from .gradebook import XlsGradeBookGroup, XlsGradeBookJury, XlsGradeBookNoGroup
from .internal import XlsStudentData
from .moodle import CsvCreateGroups, CsvGroups, CsvGroupsGroupings
from .students import SendEmail, ZoomBreakoutRooms
