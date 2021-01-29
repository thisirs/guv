"""
Fichier qui regroupe des tâches liées à la génération de calendrier
par semaine d'une UV ou d'un intervenant.
"""

import os
import re
import pandas as pd
import latex

from ..utils_config import Output
from ..utils import argument, LaTeXEnvironment
from .base import UVTask, CliArgsMixin, TaskBase
from .dodo_instructors import XlsAffectation, AddInstructors


def create_cal_from_dataframe(df, text, target):
    """Crée un calendrier avec text dans les cases"""

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

    latex_env = LaTeXEnvironment()
    template = latex_env.get_template('calendar_template.tex.jinja2')
    tex = template.render(blocks=blocks)

    # base = os.path.splitext(target)[0]
    # with open(base+'.tex', 'w') as fd:
    #     fd.write(tex)

    pdf = latex.build_pdf(tex)

    with Output(target) as target:
        pdf.save_to(target())


class CalUv(UVTask):
    """Calendrier PDF de la semaine par UV

    Crée le calendrier des Cours/TD/TP pour chaque UV sélectionnées.
    """

    target_dir = "generated"
    target_name = "calendrier.pdf"

    def setup(self):
        super().setup()
        self.uv_list = XlsAffectation.target_from(**self.info)
        self.target = self.build_target()
        jinja_dir = os.path.join(os.path.dirname(__file__), "templates")
        template = os.path.join(jinja_dir, "calendar_template.tex.jinja2")
        self.file_dep = [self.uv_list, template]

    def run(self):
        df = pd.read_excel(self.uv_list, engine="openpyxl")
        # df_uv_real = df.loc[~pd.isnull(df['Intervenants']), :]
        df_uv_real = df
        df_uv_real["Code enseig."] = self.uv

        text = r"{name} \\ {room} \\ {author}"
        return create_cal_from_dataframe(df_uv_real, text, self.target)


class CalInst(CliArgsMixin, TaskBase):
    """Calendrier PDF de la semaine par intervenant"""

    target_dir = "generated"
    target_name = "{name}_calendrier.pdf"

    cli_args = (
        argument(
            "-p",
            "--plannings",
            nargs="+",
            help="Liste des plannings à considérer",
        ),
        argument(
            "-i",
            "--insts",
            nargs="*",
            help="Liste des intervenants à considérer",
        ),
    )

    def setup(self):
        super().setup()
        self.uv_list = AddInstructors.target_from()
        jinja_dir = os.path.join(os.path.dirname(__file__), "templates")
        template = os.path.join(jinja_dir, "calendar_template.tex.jinja2")
        self.file_dep = [self.uv_list, template]

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
            create_cal_from_dataframe(df_inst, text, target)
