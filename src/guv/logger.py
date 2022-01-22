import os
import sys
import logging

from schema import Schema, Or, And, Use

LEVELS = {
    "critical": logging.CRITICAL,
    "error": logging.ERROR,
    "warn": logging.WARNING,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
}

class LogFormatter(logging.Formatter):

    formats = {
        logging.DEBUG: "DEBUG: %(message)s",
        logging.INFO: "%(message)s",
        logging.WARN: "\033[33mWARNING\033[0m: %(message)s",
        logging.ERROR: "\033[31mERROR\033[0m: %(message)s",
    }
    def formatMessage(self, record):
        return LogFormatter.formats.get(
            record.levelno, self._fmt) % record.__dict__

def get_level():
    if "DEBUG" in os.environ:
        level = os.environ["DEBUG"]
    else:
        level = logging.INFO

    schema = Schema(
        Or(
            int,
            And(str, Use(int)),
            And(str, Use(lambda s: LEVELS.get(s.lower(), logging.INFO))),
        )
    )

    return schema.validate(level)


logger = logging.getLogger("guv")
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(LogFormatter())
logger.setLevel(get_level())
logger.addHandler(handler)
