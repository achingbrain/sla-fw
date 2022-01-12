# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import logging
from logging.config import dictConfig
from typing import Dict

from slafw import defines
from slafw.errors.errors import FailedToSetLogLevel

DEFAULT_CONFIG = {
    "version": 1,
    "formatters": {"slafw": {"format": "%(levelname)s - %(name)s - %(message)s"}},
    "handlers": {
        "journald": {"class": "systemd.journal.JournalHandler", "formatter": "slafw", "SYSLOG_IDENTIFIER": "SLAFW"}
    },
    "root": {"level": "INFO", "handlers": ["journald"]},
}


def _get_config() -> Dict:
    with defines.loggingConfig.open("r") as f:
        return json.load(f)


def configure_log() -> bool:
    """
    Configure logger according to configuration file or hardcoded config

    :return: True if configuration file was used, False otherwise
    """
    try:
        dictConfig(_get_config())
        return True
    except Exception:
        dictConfig(DEFAULT_CONFIG)
        return False


def get_log_level() -> int:
    """
    Get current loglevel from configuration file

    :return: Current loglevel as LogLevel
    """
    try:
        config = _get_config()
    except Exception:
        config = DEFAULT_CONFIG
    raw_level = config["root"]["level"]
    return logging.getLevelName(raw_level)


def _set_config(config: Dict, level: int, persistent: bool):
    try:
        config["root"]["level"] = logging.getLevelName(level)
        # Setting level to root logger changes all loggers (in the same process)
        logging.getLogger().setLevel(level)

        if persistent:
            with defines.loggingConfig.open("w") as f:
                json.dump(config, f)
    except Exception as exception:
        raise FailedToSetLogLevel from exception


def set_log_level(level: int, persistent=True) -> bool:
    """
    Set log level to configuration file and runtime

    :param level: LogLevel to set
    :param persistent: True to set persisten configuration, False to set transient/runtime configuration
    :return: True if config file was used as a base, False otherwise
    """
    try:
        config = _get_config()
        base_used = True
    except Exception:
        config = DEFAULT_CONFIG
        base_used = False

    _set_config(config, level, persistent)
    return base_used
