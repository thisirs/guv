import os
from pathlib import Path
import importlib

SEMESTER_VARIABLE = "DOIT_UTC_SEMESTER_PATH"


class ConfigError(Exception):
    pass


class SettingError(Exception):
    pass


class SettingsUpdate():
    def __init__(self, *sequence):
        self.sequence = sequence
        self.config_files = [f for c in self.sequence for f in c.config_files]

    def __getattr__(self, name):
        if name.startswith("__"):  # for copy to succeed ignore __getattr__
            raise AttributeError(name)

        for settings in self.sequence[::-1]:
            try:
                return getattr(settings, name)
            except AttributeError:
                continue
        raise AttributeError(f"La variable '{name}' n'a été trouvée dans aucun fichier de configuration")

    def __contains__(self, e):
        try:
            self.__getattr__(e)
            return True
        except AttributeError:
            return False


class Settings:
    def __init__(self, directory):
        self._load_default(directory)
        self.config_files = [Path(directory) / "config.py"]
        self._load(Path(directory) / "config.py")

    def _load_default(self, directory):
        self.DEBUG = 0

    def _load(self, config_file):
        if not Path(config_file).exists():
            raise Exception(f"Le fichier '{config_file}' n'existe pas")

        module_name = os.path.splitext(os.path.basename(config_file))[0]
        spec = importlib.util.spec_from_file_location(module_name, config_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        settings = [s for s in dir(module) if s.isupper()]
        self.validate_config(settings)
        for setting in settings:
            setting_value = getattr(module, setting)
            setattr(self, setting, setting_value)

    def validate_config(settings):
        pass

    def __getattr__(self, name):
        if name.startswith("__"):  # for copy to succeed ignore __getattr__
            raise AttributeError(name)

        if name in self.__dict__:
            return self.__dict__[name]
        else:
            raise AttributeError(f"La variable '{name}' n'a pas été trouvée")

    def __contains__(self, e):
        return e in self.__dict__


class SemesterSettings(Settings):
    def _load_default(self, directory):
        super()._load_default(directory)

        self.SEMESTER = os.path.basename(directory)
        self.SEMESTER_DIR = directory
        self.DOIT_CONFIG = {
            "dep_file": os.path.join(directory, ".doit.db"),
            "default_tasks": ["utc_uv_list_to_csv"],
        }

    def validate_config(self, settings):
        required_settings = set(
            [
                "CRENEAU_UV",
                "PLANNINGS",
                "DEFAULT_INSTRUCTOR",
                "TURN",
                "SKIP_DAYS_C",
                "SKIP_DAYS_D",
                "SKIP_DAYS_T",
            ]
        )

        if not required_settings.issubset(settings):
            s = ", ".join(f"'{s}'" for s in required_settings)
            raise SettingError(f"Le fichier 'config.py' d'un semestre doit définir les variables {s}")


class UVSettings(Settings):
    def _load_default(self, directory):
        self.DOIT_CONFIG = {
            "default_tasks": ["utc_uv_list_to_csv", "xls_student_data_merge"],
            "verbosity": 2,
            "dep_file": os.path.join(directory, "../", ".doit.db"),
        }

    def validate_config(self, settings):
        required_settings = set(
            [
                "MOODLE_LISTING",
                "ENT_LISTING",
                "AFFECTATION_LISTING",
                "AGGREGATE_DOCUMENTS"
            ]
        )

        if not required_settings.issubset(settings):
            s = ", ".join(f"'{s}'" for s in required_settings)
            raise SettingError(f"Le fichier 'config.py' d'une UV doit définir les variables {s}")


if SEMESTER_VARIABLE in os.environ:
    wd = os.environ.get(SEMESTER_VARIABLE)
    semester_settings = SemesterSettings(wd)
else:
    wd = os.getcwd()

    if (Path(wd) / "config.py").exists():
        if (Path(wd).parent / "config.py").exists():
            # In UV directory
            semester_settings = SemesterSettings(str(Path(wd).parent))
            semester_settings.UV_DIR = os.path.basename(wd)
            uv_settings = UVSettings(wd)
        else:
            # In semester directory
            semester_settings = SemesterSettings(wd)
            semester_settings.UV_DIR = None
            uv_settings = ()
    else:
        raise ConfigError("Le dossier courant n'est pas reconnu comme un dossier de semestre ou un dossier d'UV")

