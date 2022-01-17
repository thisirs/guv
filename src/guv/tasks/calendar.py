"""
Ce module rassemble les tâches liées à la génération de calendrier par
semaine d'une UV ou d'un intervenant.
"""

import os
import re

import latex
import pandas as pd

import guv

from ..utils import argument
from ..utils_config import render_from_contexts
from .base import CliArgsMixin, TaskBase, UVTask
from .instructors import AddInstructors, XlsAffectation


def create_cal_from_dataframe(df, text, target, save_tex=False):
    """Crée un calendrier des créneaux dans `df`.

    `text` dans les cases.

    """

    # 08:15 should be 8_15
    def convert_time(time):
        time = time.replace(':', '_')
        return re.sub('^0', '', time)

    def convert_day(day):
        mapping = {'Lundi': 'Lun',
                   'Mardi': 'Mar',
                   'Mercredi': 'Mer',
                   'Jeudi': 'Jeu',
                   'Vendredi': 'Ven',
                   'Samedi': 'Sam',
                   'Dimanche': 'Dim'}
        return mapping[day]

    def convert_author(author):
        parts = re.split('[ -]', author)
        return ''.join(e[0].upper() for e in parts)

    # Returns blocks like \node[2hours, full, {course}] at ({day}-{bh}) {{{text}}};
    def build_block(row, text, half=False):
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

        if 'Intervenants' in row.keys():
            if pd.isnull(row['Intervenants']):
                author = 'N/A'
            else:
                author = convert_author(row['Intervenants'])
        else:
            author = 'N/A'

        room = row['Locaux']
        if isinstance(room, str):
            room = room.replace(' ', '').replace('BF', 'F')
        else:
            room = ""

        text = text.format(room=room, name=name, author=author, uv=uv)

        # if half:
        #     text = r"""
        #     \begin{fitbox}{1.4cm}{1.8cm}
        #     \begin{center}
        #     (((text)))
        #     \end{center}
        #     \end{fitbox}
        #     """.replace('(((text)))', text)

        bh = convert_time(row['Heure début'])
        day = convert_day(row['Jour'])

        if not half:
            half = 'full'
        return rf'\node[2hours, {half}, {ctype}] at ({day}-{bh}) {{{text}}};'

    def generate_contexts():
        blocks = []
        for hour, group in df.groupby(['Jour', 'Heure début', 'Heure fin']):
            if len(group) > 2:
                raise Exception("Trop de créneaux en même temps")
            elif len(group) == 2:
                group = group.sort_values('Semaine')
                block1 = build_block(group.iloc[0], text, half='atleft')
                block2 = build_block(group.iloc[1], text, half='atright')
                blocks += [block1, block2]
            elif len(group) == 1:
                block = build_block(group.iloc[0], text)
                blocks.append(block)

        blocks = '\n'.join(blocks)

        yield {"blocks": blocks, "filename_no_ext": os.path.basename(target)}

    contexts = generate_contexts()
    template = 'calendar_template.tex.jinja2'
    render_from_contexts(template, contexts, target=target, save_tex=save_tex)


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
        self.uv_list = XlsAffectation.target_from(**self.info)
        self.target = self.build_target()
        tmpl_dir = os.path.join(guv.__path__[0], "templates")
        template = os.path.join(tmpl_dir, "calendar_template.tex.jinja2")
        self.file_dep = [self.uv_list, template]
        self.parse_args()

    def run(self):
        df = pd.read_excel(self.uv_list, engine="openpyxl")
        # df_uv_real = df.loc[~pd.isnull(df['Intervenants']), :]
        df_uv_real = df
        df_uv_real["Code enseig."] = self.uv

        text = r"{name} \\ {room} \\ {author}"
        create_cal_from_dataframe(df_uv_real, text, self.target, save_tex=self.save_tex)


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
            nargs="+",
            help="Spécifie les UV/UE concernées via les plannings. Par défaut, toutes les UV/UE des plannings ``SELECTED_PLANNINGS`` sont concernées.",
        ),
        argument(
            "-i",
            "--insts",
            nargs="*",
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
        self.uv_list = AddInstructors.target_from()
        tmpl_dir = os.path.join(guv.__path__[0], "templates")
        template = os.path.join(tmpl_dir, "calendar_template.tex.jinja2")
        self.file_dep = [self.uv_list, template]

        self.parse_args()
        if self.plannings is None:
            self.plannings = self.settings.SELECTED_PLANNINGS
        if self.insts is None:
            self.insts = [self.settings.DEFAULT_INSTRUCTOR]

        def build_prefix(inst):
            return f'{inst.replace(" ", "_")}_{"_".join(self.plannings)}'

        self.targets = [
            self.build_target(name=build_prefix(inst))
            for inst in self.insts
        ]

    def run(self):
        for inst, target in zip(self.insts, self.targets):
            df = pd.read_csv(self.uv_list)
            if "Intervenants" not in df.columns:
                raise Exception("Pas d'enregistrement des intervenants")

            df_inst = df.loc[
                (df["Intervenants"].astype(str) == inst)
                & (df["Planning"].isin(self.plannings)),
                :,
            ]
            text = r"{uv} \\ {name} \\ {room}"
            create_cal_from_dataframe(df_inst, text, target, save_tex=self.save_tex)
