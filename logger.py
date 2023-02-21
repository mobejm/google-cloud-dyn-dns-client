import logging.config
import os
import yaml
import sys

default_logging_config = "logging.yaml"
default_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "loggers": {
        "root": {
            "level": "INFO",
            "handlers": ["consoleHandler"]
        }
    },
    "handlers": {
        "consoleHandler": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": "ext://sys.stdout"
        }
    },
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            # Due to what seems to be a bug in JsonFormatter, both {level} and {levelname} must be included in the format string but
            # the field will only be included once due to the rename
            "format": "%(timestamp)s %(level)s %(levelname)s %(app)s %(name)s %(threadName)s %(funcName)s %(message)s",
            "timestamp": True,
            "static_fields": {
                "app": "dyn-dns-client"
            },
            "rename_fields": {
                "levelname": "level"
            }
        }
    }
}

def _setup_default_logging():
    logging.config.dictConfig(config=default_config)

if os.path.isfile(default_logging_config):
    with open(default_logging_config, "r") as stream:
        try:
            print(f"Loading logging configuration from {default_logging_config}.")
            logging_config = (yaml.safe_load(stream))
            logging.config.dictConfig(logging_config)
        except Exception as exc:
            print(f"{exc}", file=sys.stderr)
            print(f"########################################################################################", file=sys.stderr)
            print(f"WARNING: Failed to load logging configuration file. Will use default logging parameters.", file=sys.stderr)
            print(f"########################################################################################", file=sys.stderr)
            _setup_default_logging()
else:
    _setup_default_logging()