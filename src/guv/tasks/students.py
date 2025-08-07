import getpass
import os
import smtplib

import jinja2
import pandas as pd

from ..exceptions import GuvUserError
from ..logger import logger
from ..translations import TaskDocstring, _
from ..utils import argument, normalize_string
from ..utils_config import Output, ask_choice
from .base import CliArgsMixin, UVTask
from .internal import XlsStudentData


__all__ = ["SendEmail", "ZoomBreakoutRooms"]


class ZoomBreakoutRooms(UVTask, CliArgsMixin):
    __doc__ = TaskDocstring()

    target_dir = "generated"
    target_name = "zoom_breakout_rooms_{group}.csv"
    cli_args = (
        argument(
            "group",
            help=_("The name of the group column"),
        ),
    )

    def setup(self):
        super().setup()
        self.xls_merge = XlsStudentData.target_from(**self.info)
        self.file_dep = [self.xls_merge]
        self.parse_args()
        self.target = self.build_target(group=normalize_string(self.group, type="file"))

    def run(self):
        df = XlsStudentData.read_target(self.xls_merge)
        self.check_if_present(
            df, self.group, file=self.xls_merge, base_dir=self.settings.SEMESTER_DIR
        )

        email_column = self.settings.EMAIL_COLUMN
        df_group = pd.DataFrame({
            "Pre-assign Room Name": df[self.group],
            "Email Address": df[email_column]
        })
        df_group = df_group.sort_values("Pre-assign Room Name")
        with Output(self.target, protected=True) as out:
            df_group.to_csv(out.target, index=False)


class SendEmail(UVTask, CliArgsMixin):
    __doc__ = TaskDocstring()

    uptodate = False
    cli_args = (
        argument(
            "template",
            help=_("The path to a Jinja2 template"),
        ),
    )

    def setup(self):
        super().setup()
        self.xls_merge = XlsStudentData.target_from(**self.info)
        self.file_dep = [self.xls_merge]
        self.parse_args()

    def run(self):
        if os.path.exists(self.template):
            self.send_emails()
        else:
            self.create_template()

    def create_template(self):
        result = ask_choice(
            _("The file {template} does not exist. Create? (y/n) ").format(template=self.template),
            {"y": True, "n": False},
        )
        if result:
            with open(self.template, "w") as file_:
                file_.write(_("Subject: subject\n\nbody"))

    def send_emails(self):
        df = XlsStudentData.read_target(self.xls_merge)

        with open(self.template, "r") as file_:
            if not file_.readline().startswith("Subject:"):
                raise GuvUserError(_("Message must start with \"Subject:\""))

        jinja_env = jinja2.Environment(loader=jinja2.BaseLoader(), undefined=jinja2.StrictUndefined)
        with open(self.template) as f:
            template_str = f.read()
        message_tmpl = jinja_env.from_string(template_str)
        message_tmpl = jinja_env.get_template(self.template)

        try:
            email_and_message = [
                (row[self.settings["EMAIL_COLUMN"]], message_tmpl.render(row.to_dict()))
                for index, row in df.iterrows()
            ]
        except jinja2.exceptions.UndefinedError as e:
            raise e

        if len(email_and_message) == 0:
            raise GuvUserError(_("No message to send"))

        email, message = email_and_message[0]
        logger.info(_("First message to {email}: \n{message}").format(email=email, message=message))
        result = ask_choice(
            _("Send the {n} emails? (y/n) ").format(n=len(email_and_message)),
            {"y": True, "n": False},
        )

        if result:
            from_email = self.settings.FROM_EMAIL

            with smtplib.SMTP(
                self.settings.SMTP_SERVER, port=self.settings.PORT
            ) as smtp:
                smtp.starttls()

                password = getpass.getpass(_("Password: "))
                smtp.login(self.settings.LOGIN, password)
                for email, message in email_and_message:
                    smtp.sendmail(from_addr=from_email, to_addrs=email, msg=message)


