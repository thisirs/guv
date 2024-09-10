"""
Ce module rassemble les tâches liées à la génération de calendrier par
semaine d'une UV ou d'un intervenant.
"""

import os
import re

import pandas as pd

import guv

from ..logger import logger
from ..utils import argument, ps, px, normalize_string
from ..utils_config import render_from_contexts
from .base import CliArgsMixin, TaskBase, UVTask
from .utc import WeekSlots, WeekSlotsAll


class InvalidBlock(Exception):
    def __str__(self):
        row = self.args[0]
        beg, end = row["Heure début"].strftime("%H:%M"), row["Heure fin"].strftime("%H:%M")
        return f"{row['Jour']} de {beg} à {end}"


def convert_day(day):
    mapping = {'Lundi': 'Lun',
               'Mardi': 'Mar',
               'Mercredi': 'Mer',
               'Jeudi': 'Jeu',
               'Vendredi': 'Ven',
               'Samedi': 'Sam',
               'Dimanche': 'Dim'}
    return mapping[day]


def build_block(row, template, location="full"):
    """Return Tikz node for calendar."""

    uv = row['Code enseig.']

    name = row['Lib. créneau'].replace(' ', '')
    if re.match('^T', name):
        ctype = 'TP'
        if isinstance(row['Semaine'], str):
            name = name + row['Semaine']
    elif re.match('^D', name):
        ctype = 'TD'
    elif re.match('^C', name):
        ctype = 'Cours'

    if pd.isnull(row['Abbrev']):
        author = 'N/A'
    else:
        author = row["Abbrev"]

    room = row['Locaux']
    if isinstance(room, str):
        room = room.replace(' ', '').replace('BF', 'F')
    else:
        room = "N/A"

    text = template.format(room=room, name=name, author=author, uv=uv)

    time_beg, time_end = row["Heure début"], row["Heure fin"]

    if time_beg.minute not in [0, 15, 30, 45]:
        raise InvalidBlock(row)

    if time_end.minute not in [0, 15, 30, 45]:
        raise InvalidBlock(row)

    if time_beg.hour not in [8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]:
        raise InvalidBlock(row)

    if time_end.hour not in [8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]:
        raise InvalidBlock(row)

    bh = time_beg.strftime("%H_%M")
    eh = time_end.strftime("%H_%M")
    day = convert_day(row['Jour'])

    if location == "left":
        return rf"\node[draw, {ctype}, fit={{({day}-{bh}) ({day}-{eh}-half)}}] {{{text}}};"
    elif location == "right":
        return rf"\node[draw, {ctype}, fit={{({day}-{bh}-half) ({day}-{eh}-end)}}] {{{text}}};"
    elif location == "full":
        return rf"\node[draw, {ctype}, fit={{({day}-{bh}) ({day}-{eh}-end)}}] {{{text}}};"
    else:
        raise RuntimeError("`location` must be `left`, `right` or `full`")


def create_cal_from_dataframe(df, template, target, save_tex=False):
    """Crée un calendrier des créneaux présents dans `df`.

    `template` dans les cases.

    """

    blocks = []
    for hour, group in df.groupby(['Jour', 'Heure début', 'Heure fin']):
        try:
            if len(group) > 2:
                raise Exception("Trop de créneaux en même temps")
            elif len(group) == 2:
                group = group.sort_values('Semaine')
                block1 = build_block(group.iloc[0], template, location='left')
                block2 = build_block(group.iloc[1], template, location='right')
                blocks += [block1, block2]
            elif len(group) == 1:
                block = build_block(group.iloc[0], template, location="full")
                blocks.append(block)
        except InvalidBlock as e:
            logger.warning("Créneau invalide ignoré : %s", e)
            continue

    context = {"blocks": blocks, "filename_no_ext": os.path.basename(target)}
    jinja2_template = 'calendar_template.tex.jinja2'
    render_from_contexts(jinja2_template, [context], target=target, save_tex=save_tex)


class CalUv(UVTask, CliArgsMixin):
    """Calendrier PDF de la semaine par UV.

    Crée le calendrier hebdomadaire des Cours/TD/TP pour chaque UV
    sélectionnée. Le fichier pdf est placé dans le sous-dossier
    ``documents`` respectif de chaque UV avec le nom
    ``calendrier_hebdomadaire.pdf``.

    """

    target_dir = "documents"
    target_name = "calendrier_hebdomadaire"
    unique_uv = False

    cli_args = (
        argument(
            "--save-tex",
            action="store_true",
            default=False,
            help="Permet de laisser les fichiers .tex générés pour modification éventuelle."
        ),
    )

    def setup(self):
        super().setup()
        self.week_slots = WeekSlots.target_from(**self.info)
        self.target = self.build_target()
        tmpl_dir = os.path.join(guv.__path__[0], "data", "templates")
        template = os.path.join(tmpl_dir, "calendar_template.tex.jinja2")
        self.file_dep = [self.week_slots, template]
        self.parse_args()

    def run(self):
        df = WeekSlots.read_target(self.week_slots)

        if df["Intervenants"].isnull().any():
            logger.warning("Certains créneaux n'ont pas d'intervenant renseigné")

        df["Code enseig."] = self.uv

        text = r"{name} \\ {room} \\ {author}"
        create_cal_from_dataframe(df, text, self.target, save_tex=self.save_tex)


class CalInst(CliArgsMixin, TaskBase):
    """Calendrier hebdomadaire par intervenant.

    {options}

    Examples
    --------

    .. code:: bash

       guv cal_inst --plannings P2048 Master2Sem1 --insts "Bob Arctor" "Winston Smith"

    """

    target_dir = "generated"
    target_name = "{name}_calendrier"

    cli_args = (
        argument(
            "-p",
            "--plannings",
            nargs="*",
            default=None,
            help="Spécifie les UV/UE concernées via les plannings. Par défaut, toutes les UV/UE des plannings configurées dans ``PLANNINGS`` sont concernées.",
        ),
        argument(
            "-i",
            "--insts",
            nargs="*",
            default=None,
            help="Spécifie la liste des intervenants pour qui créer le calendrier. Par défaut, la liste se limite à ``DEFAULT_INSTRUCTOR``.",
        ),
        argument(
            "--save-tex",
            action="store_true",
            default=False,
            help="Permet de laisser les fichiers .tex générés pour modification éventuelle."
        )
    )

    def setup(self):
        super().setup()
        self.week_slots_all = WeekSlotsAll.target_from()
        tmpl_dir = os.path.join(guv.__path__[0], "data", "templates")
        template = os.path.join(tmpl_dir, "calendar_template.tex.jinja2")
        self.file_dep = [self.week_slots_all, template]

        self.parse_args()
        if self.plannings is None:
            self.plannings = self.settings.PLANNINGS.keys()
        if self.insts is None:
            self.insts = [self.settings.DEFAULT_INSTRUCTOR]

        def build_prefix(inst):
            return f'{normalize_string(inst, type="file_no_space")}_{"_".join(self.plannings)}'

        self.targets = [
            self.build_target(name=build_prefix(inst))
            for inst in self.insts
        ]

    def run(self):
        df = WeekSlotsAll.read_target(self.week_slots_all)

        for inst, target in zip(self.insts, self.targets):
            df_inst = df.loc[
                (df["Intervenants"].astype(str) == inst)
                & (df["Planning"].isin(self.plannings)),
                :,
            ]
            if len(df_inst) == 0:
                log_function = logger.warning
            else:
                log_function = logger.info

            log_function(
                "%d créneau%s pour `%s` pour le%s planning%s : %s",
                len(df_inst),
                px(len(df_inst)),
                inst,
                ps(len(self.plannings)),
                ps(len(self.plannings)),
                ", ".join(f"`{p}`" for p in self.plannings),
            )

            text = r"{uv} \\ {name} \\ {room}"

            create_cal_from_dataframe(df_inst, text, target, save_tex=self.save_tex)
