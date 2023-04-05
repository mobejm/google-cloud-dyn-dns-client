import logging
import logging.config

from datetime import datetime
from logging.handlers import MemoryHandler
from unittest import TestCase
from typing import Callable

default_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "loggers": {
        "root": {"level": "DEBUG", "handlers": ["memoryHandler", "consoleHandler"]}
    },
    "handlers": {
        "memoryHandler": {
            "class": "logging.handlers.MemoryHandler",
            "capacity": 100,
            "formatter": "json",
        },
        "consoleHandler": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": "ext://sys.stdout",
        },
    },
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(timestamp)s %(levelname)s %(app)s %(name)s %(threadName)s %(funcName)s %(message)s",
            "timestamp": True,
        }
    },
}

logging.config.dictConfig(config=default_config)
logger = logging.getLogger(__name__)


class LogAssertions:
    def __init__(self, log_record: logging.LogRecord) -> None:
        self._log_record = log_record

    @classmethod
    def assert_last_log(self) -> "LogAssertions":
        return self.assert_nth_to_last_log(1)

    @classmethod
    def assert_nth_to_last_log(self, n: int) -> "LogAssertions":
        for handler in logger.root.handlers:
            if type(handler) is MemoryHandler:
                if len(handler.buffer) > 0:
                    return LogAssertions(handler.buffer[n * -1])
                return LogAssertions(None)
        raise ValueError(
            "LogAssertions requires a logging.handlers.MemoryHandler to be used."
        )

    @classmethod
    def assert_last_debug_log(self) -> "LogAssertions":
        return self._assert_last_log_with_level("DEBUG")

    @classmethod
    def assert_last_info_log(self) -> "LogAssertions":
        return self._assert_last_log_with_level("INFO")

    @classmethod
    def assert_last_warn_log(self) -> "LogAssertions":
        return self._assert_last_log_with_level("WARNING")

    @classmethod
    def assert_last_error_log(self) -> "LogAssertions":
        return self._assert_last_log_with_level("ERROR")

    @classmethod
    def _assert_last_log_with_level(self, level: str) -> "LogAssertions":
        for handler in logger.root.handlers:
            if type(handler) is MemoryHandler:
                for cnt in range(len(handler.buffer) - 1, -1, -1):
                    if handler.buffer[cnt].levelname.upper() == level.upper():
                        return LogAssertions(handler.buffer[cnt])
                return LogAssertions(None)
        raise ValueError(
            "LogAssertions requires a logging.handlers.MemoryHandler to be used."
        )

    def print(self) -> "LogAssertions":
        print(self._log_record)
        return self

    def exists(self) -> "LogAssertions":
        if self._log_record is None:
            raise ValueError("Expected Logrecord doesn't exist")
        return self

    def has_message_containing(self, msg: str) -> "LogAssertions":
        if msg.lower() not in self._log_record.getMessage().lower():
            raise ValueError(
                f'The string "{self._log_record.getMessage()}" was expected to contain "{msg}".'
            )
        return self

    def is_info(self) -> "LogAssertions":
        return self.is_level("INFO")

    def is_warning(self) -> "LogAssertions":
        return self.is_level("WARNING")

    def is_error(self) -> "LogAssertions":
        return self.is_level("ERROR")

    def is_level(self, level: str) -> "LogAssertions":
        if not self._log_record.levelname.upper() == level.upper():
            raise ValueError(
                f"Expected log level to be {level} but it was {self._log_record.levelname.upper()}."
            )
        return self

    def is_newer_than(self, timestamp: int) -> "LogAssertions":
        log_utc_timestamp = datetime.utcfromtimestamp(
            self._log_record.created
        ).timestamp()
        if timestamp >= log_utc_timestamp:
            raise ValueError(
                f"LogRecord was created on {log_utc_timestamp}, but was expected to be newer than {timestamp}."
            )
        return self
