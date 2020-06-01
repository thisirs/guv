import os
import pandas as pd

from .config import settings
from .utils import (
    add_templates,
    documents,
    generated,
    selected_uv,
    create_cal_from_dataframe,
    parse_args,
    argument,
    actionfailed_on_exception,
)

from .dodo_instructors import task_xls_affectation, task_add_instructors


@add_templates(target="calendrier.pdf")
def task_cal_uv():
    """Calendrier PDF de la semaine globale des UV sélectionnées

Crée le calendrier des Cours/TD/TP pour chaque UV sélectionnées.
    """

    def create_cal_from_list(uv, uv_list_filename, target):
        df = pd.read_excel(uv_list_filename)
        # df_uv_real = df.loc[~pd.isnull(df['Intervenants']), :]
        df_uv_real = df
        df_uv_real["Code enseig."] = uv

        text = r"{name} \\ {room} \\ {author}"
        return create_cal_from_dataframe(df_uv_real, text, target)

    jinja_dir = os.path.join(os.path.dirname(__file__), "templates")
    template = os.path.join(jinja_dir, "calendar_template.tex.jinja2")

    for planning, uv, info in selected_uv():
        uv_list = documents(task_xls_affectation.target, **info)
        target = generated(task_cal_uv.target, **info)

        yield {
            "name": f"{planning}_{uv}",
            "file_dep": [uv_list, template],
            "targets": [target],
            "actions": [(create_cal_from_list, [uv, uv_list, target])],
        }


@actionfailed_on_exception
def task_cal_inst():
    """Calendrier PDF d'une semaine de toutes les UV/UE d'un intervenant."""

    def create_cal_from_list(inst, plannings, uv_list_filename, target):
        df = pd.read_csv(uv_list_filename)
        if "Intervenants" not in df.columns:
            raise Exception("Pas d'enregistrement des intervenants")

        df_inst = df.loc[
            (df["Intervenants"].astype(str) == inst) & (df["Planning"].isin(plannings)),
            :,
        ]
        text = r"{uv} \\ {name} \\ {room}"
        create_cal_from_dataframe(df_inst, text, target)

    args = parse_args(
        task_cal_inst,
        argument(
            "-p",
            "--plannings",
            nargs="*",
            default=settings.SELECTED_PLANNINGS,
            help="Liste des plannings à considérer",
        ),
        argument(
            "-i",
            "--insts",
            nargs="*",
            default=[settings.DEFAULT_INSTRUCTOR],
            help="Liste des intervenants à considérer",
        ),
    )

    uv_list = generated(task_add_instructors.target)
    jinja_dir = os.path.join(os.path.dirname(__file__), "templates")
    template = os.path.join(jinja_dir, "calendar_template.tex.jinja2")

    for inst in args.insts:
        target = generated(
            f'{inst.replace(" ", "_")}_{"_".join(args.plannings)}_calendrier.pdf'
        )

        yield {
            "name": "_".join(args.plannings) + "_" + inst,
            "targets": [target],
            "file_dep": [uv_list, template],
            "actions": [
                (create_cal_from_list, [inst, args.plannings, uv_list, target])
            ],
        }
