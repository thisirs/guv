import os
import glob
import tempfile
import zipfile
import pandas as pd

from doit.exceptions import TaskFailed

from .config import settings
from .utils import (
    Output,
    generated,
    compute_slots,
    ical_events,
    parse_args,
    argument,
    actionfailed_on_exception,
)
from .dodo_instructors import task_add_instructors


@actionfailed_on_exception
def task_ical_inst():
    """Fichier iCal de tous les créneaux des intervenants

    Crée un fichier iCal de tous les créneaux de Cours/TP/TD du ou des
    plannings renseignés pour les intervenants renseignés.
    """

    def create_ical_inst(insts, plannings, csv):
        tables = [
            compute_slots(csv, ptype, empty_instructor=False) for ptype in plannings
        ]
        dfm = pd.concat(tables)

        all_insts = dfm["Intervenants"].unique()
        if len(insts) == 1 and insts[0] == "all":
            insts = all_insts

        if set(insts).issubset(set(all_insts)):
            if len(insts) == 1:
                inst = insts[0]
                dfm_inst = dfm.loc[dfm["Intervenants"].astype(str) == inst, :]
                output = generated(f'{inst.replace(" ", "_")}.ics')
                events = ical_events(dfm_inst)
                with Output(output) as output:
                    with open(output(), "wb") as fd:
                        fd.write(events)
            else:
                temp_dir = tempfile.mkdtemp()
                for inst in insts:
                    dfm_inst = dfm.loc[dfm["Intervenants"].astype(str) == inst, :]
                    events = ical_events(dfm_inst)

                    output = f'{inst.replace(" ", "_")}.ics'
                    with open(os.path.join(temp_dir, output), "wb") as fd:
                        fd.write(events)

                output = generated(f"ics.zip")
                with Output(output) as output0:
                    with zipfile.ZipFile(output0(), "w") as z:
                        for filepath in glob.glob(os.path.join(temp_dir, "*.ics")):
                            z.write(filepath, os.path.basename(filepath))

        else:
            unknown = set(insts).difference(all_insts)
            return TaskFailed(f"Intervenant(s) inconnu(s): {', '.join(unknown)}")

    args = parse_args(
        task_ical_inst,
        argument(
            "-p",
            "--plannings",
            nargs="+",
            default=settings.SELECTED_PLANNINGS,
            help="Liste des plannings à considérer",
        ),
        argument(
            "-i",
            "--insts",
            nargs="+",
            default=[settings.DEFAULT_INSTRUCTOR],
            help="Liste des intervenants à considérer",
        ),
    )

    deps = [generated(task_add_instructors.target)]

    return {
        "actions": [(create_ical_inst, [args.insts, args.plannings, deps[0]])],
        "file_dep": deps,
        "uptodate": [False],
        "verbosity": 2,
    }
