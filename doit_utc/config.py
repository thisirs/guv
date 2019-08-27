import os
import importlib

CONFIG_VARIABLE = "SETTINGS_FILES"


class Settings:
    def __init__(self):
        settings_files = os.environ.get(CONFIG_VARIABLE)
        if not settings_files:
            raise Exception(f"Pas de fichier de configuration dans {CONFIG_VARIABLE}")
        self.settings_files = settings_files
        self._loaded = False

    def _setup(self):
        for settings_file in self.settings_files.split(","):
            module_name = os.path.splitext(os.path.basename(settings_file))[0]
            spec = importlib.util.spec_from_file_location(module_name, settings_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            for setting in dir(module):
                if setting.isupper():
                    setting_value = getattr(module, setting)
                    setattr(self, setting, setting_value)

    def __contains__(self, e):
        return e in self.__dict__

    def __getattr__(self, name):
        if not self._loaded:
            self._setup()
            self._loaded = True
        if name in self.__dict__:
            return self.__dict__[name]
        else:
            raise AttributeError


settings = Settings()
