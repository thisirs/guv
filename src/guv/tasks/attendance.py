from jinja2 import Template

from ..exceptions import GuvUserError
from ..translations import _, TaskDocstring
from ..utils import (argument, generate_groupby, make_groups,
                     normalize_string, sort_values, get_latex_template)
from ..utils_config import render_from_contexts
from .base import CliArgsMixin, UVTask
from .internal import XlsStudentData


__all__ = ["PdfAttendance", "PdfAttendanceFull"]


class PdfAttendance(UVTask, CliArgsMixin):
    __doc__ = TaskDocstring()

    uptodate = False
    target_dir = "generated"
    target_name = "{title}_{group}"
    template_file = "attendance.tex.jinja2"

    cli_args = (
        argument(
            "-t",
            "--title",
            default=_("Attendance sheet"),
            help=_("Specifies a title that will be used in the attendance sheets and the name of the generated file. By default, it is ``%(default)s``.")
        ),
        argument(
            "-g",
            "--group",
            help=_("Allows creating groups to make as many attendance sheets. You must specify a column from the central file ``effectif.xlsx``."),
        ),
        argument(
            "-b",
            "--blank",
            action="store_true",
            default=False,
            help=_("Do not display the names of the students (useful only with --group).")
        ),
        argument(
            "-c",
            "--count",
            type=int,
            nargs="*",
            help=_("Uses a list of staff instead of ``--group``. The group names can be specified by ``--names``. Otherwise, the group names are in the form ``Group 1``, ``Group 2``,...")
        ),
        argument(
            "-n",
            "--names",
            nargs="*",
            help=_("Specifies the names of the groups corresponding to ``--count``. The list must be the same size as ``--count``.")
        ),
        argument(
            "-e",
            "--extra",
            type=int,
            default=0,
            help=_("Allows adding additional empty lines in addition to those already present induced by ``--group`` or set by ``--count``.")
        ),
        argument(
            "--tiers-temps",
            nargs="?",
            const=_("Extra time"),
            default=None,
            help=_("Specifies the column for students placed in a dedicated room. If the column is not specified, ``%(default)s``.")
        ),
        argument(
            "--save-tex",
            action="store_true",
            default=False,
            help=_("Allows leaving the generated .tex files for possible modification.")
        )
    )

    def setup(self):
        super().setup()
        self.xls_merge = XlsStudentData.target_from(**self.info)
        self.file_dep = [self.xls_merge]

        self.parse_args()
        self.target = self.build_target(
            group=normalize_string(self.group, type="file_no_space") if self.group else "all",
            title=normalize_string(self.title, type="file_no_space")
        )

    def generate_contexts(self):
        "Generate contexts to pass to Jinja2 templates."

        if self.group and self.count:
            self.parser.error(_("The options --group and --count are incompatible"))

        # Common context
        context = {
            "title": self.title,
            "extra": self.extra,
            **self.info
        }

        if self.count:
            if self.names:
                if len(self.count) != len(self.names):
                    self.parser.error(_("The options --count and --names must be of the same length"))
            else:
                self.names = [_("Group_{i}").format(i=i+1) for i in range(len(self.count))]

            if self.blank:
                context["blank"] = True
                for num, name in zip(self.count, self.names):
                    context["group"] = name
                    context["num"] = num
                    context["filename_no_ext"] = f"{name}"
                    yield context
            else:
                df = XlsStudentData.read_target(self.xls_merge)

                columns = [self.settings.LASTNAME_COLUMN, self.settings.NAME_COLUMN]
                self.check_if_present(df, columns, file=self.xls_merge)

                df = sort_values(df, columns)
                context["blank"] = False

                if self.tiers_temps is not None:
                    self.check_if_present(
                        df, self.tiers_temps, file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR
                    )
                    if not df[self.tiers_temps].isin(["Oui", "Non"]).all():
                        raise GuvUserError(_("The column `{self.tiers_temps}` must contain only Yes/No").format(tiers_temps=self.tiers_temps))

                    df_tt = df[df[self.tiers_temps] == "Oui"]
                    df = df[df[self.tiers_temps] != "Oui"]
                    context["group"] = _("Dedicated room")
                    context["filename_no_ext"] = _("Extra_time")
                    students = [{"name": f'{row[self.settings.LASTNAME_COLUMN]} {row[self.settings.NAME_COLUMN]}'} for _, row in df_tt.iterrows()]
                    context["students"] = students
                    yield context

                if sum(self.count) < len(df.index):
                    raise GuvUserError(_("The cumulative numbers are not sufficient"))

                groups = make_groups(df.index, self.count)
                for name, idxs in zip(self.names, groups):
                    group = df.loc[idxs]
                    print(name, ":", " ".join(group.iloc[0][columns]), "--",
                          " ".join(group.iloc[-1][columns]))
                    students = [{"name": f'{row[self.settings.LAST_NAME_COLUMN]} {row[self.settings.NAME_COLUMN]}'} for _, row in group.iterrows()]
                    context["students"] = students
                    context["filename_no_ext"] = f"{name}"
                    context["group"] = name
                    yield context

        else:
            df = XlsStudentData.read_target(self.xls_merge)
            columns = [self.settings.LASTNAME_COLUMN, self.settings.NAME_COLUMN]
            self.check_if_present(df, columns, file=self.xls_merge)

            df = sort_values(df, columns)

            if self.tiers_temps:
                self.check_if_present(
                    df, self.tiers_temps, file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR
                )
                if not df[self.tiers_temps].isin(["Oui", "Non"]).all():
                    raise GuvUserError(_("The column `{tiers_temps}` must contain only Yes/No").format(tiers_temps=self.tiers_temps))

                df_tt = df[df[self.tiers_temps] == "Oui"]
                df = df[df[self.tiers_temps] != "Oui"]

                context["group"] = _("Dedicated room")
                context["blank"] = self.blank
                context["num"] = len(df_tt)
                context["filename_no_ext"] = _("Extra_time")
                students = [{"name": f'{row[self.settings.LASTNAME_COLUMN]} {row[self.settings.NAME_COLUMN]}'} for _, row in df_tt.iterrows()]
                context["students"] = students
                yield context

            if self.group is not None:
                self.check_if_present(
                    df, self.group, file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR
                )

            groups = list(generate_groupby(df, self.group, ascending=True))

            if self.names and len(groups) != len(self.names):
                raise GuvUserError(_("The number of names specified with --names is different from the number of groups"))

            for i, (gn, group) in enumerate(groups):
                # Override group name if self.names
                if self.names:
                    gn = self.names[i]

                context["group"] = gn
                context["blank"] = self.blank
                context["num"] = len(group)
                context["filename_no_ext"] = f"{gn}" or normalize_string(self.title, type="filename_no_ext")
                students = [{"name": f'{row[self.settings.LASTNAME_COLUMN]} {row[self.settings.NAME_COLUMN]}'} for _, row in group.iterrows()]
                context["students"] = students
                yield context

    def run(self):
        contexts = self.generate_contexts()

        template = get_latex_template(self.template_file)
        render_from_contexts(
            template, contexts, save_tex=self.save_tex, target=self.target
        )


class PdfAttendanceFull(UVTask, CliArgsMixin):
    __doc__ = TaskDocstring()

    target_dir = "generated"
    target_name = "{title}_{group}_full"
    template_file = "attendance_name_full.tex.jinja2"
    uptodate = True
    cli_args = (
        argument(
            "--title",
            default=_("Attendance sheet"),
            help=_("Specifies a title that will be used in the attendance sheets and the name of the generated file. By default, it is ``%(default)s``.")
        ),
        argument(
            "-g",
            "--group",
            help=_("Allows specifying a group column to make attendance sheets by groups."),
        ),
        argument(
            "-n",
            "--slots",
            required=True,
            type=int,
            help=_("Allows specifying the number of sessions for the semester, i.e., the number of columns in the attendance sheet."),
        ),
        argument(
            "-t",
            "--template",
            default="S{{number}}",
            help=_("Template to set the name of successive sessions in the attendance sheet. By default, it is ``%(default)s``. The only supported keyword is ``number`` which starts at 1."),
        ),
        argument(
            "--save-tex",
            action="store_true",
            default=False,
            help=_("Allows leaving the generated .tex files for possible modification.")
        )
    )

    def setup(self):
        super().setup()
        self.xls_merge = XlsStudentData.target_from(**self.info)
        self.file_dep = [self.xls_merge]
        self.parse_args()
        self.target = self.build_target(
            title=normalize_string(self.title, type="file_no_space"),
            group=normalize_string(self.group, type="file_no_space") if self.group else "all"
        )

    def run(self):
        df = XlsStudentData.read_target(self.xls_merge)
        if self.group is not None:
            self.check_if_present(
                df, self.group, file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR
            )

        contexts = self.generate_contexts(df)

        template = get_latex_template(self.template_file)
        render_from_contexts(
            template, contexts, save_tex=self.save_tex, target=self.target
        )

    def generate_contexts(self, df):
        base_context = {
            "slots_name": [
                Template(self.template).render(number=i+1)
                for i in range(self.slots)
            ],
            **self.info,
            "nslot": self.slots,
            "title": self.title
        }

        key = (lambda x: "all") if self.group is None else self.group

        columns = [self.settings.LASTNAME_COLUMN, self.settings.NAME_COLUMN]
        self.check_if_present(df, columns, file=self.xls_merge)

        for gn, group in df.groupby(key):
            group = sort_values(group, columns)

            students = [
                {"name": f'{row[self.settings.LASTNAME_COLUMN]} {row[self.settings.NAME_COLUMN]}'} for _, row in group.iterrows()
            ]
            group_context = {
                "group": None if gn == "all" else gn,
                "filename_no_ext": gn,
                "students": students,
            }
            yield {**base_context, **group_context}
