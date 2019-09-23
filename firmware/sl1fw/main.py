#!/usr/bin/env python

# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import os
import json
import logging
from logging.config import dictConfig
import gettext
import builtins as builtins

from sl1fw import defines

try:
    with open(defines.loggingConfig, 'r') as f:
        logDict = json.load(f)
    #endwith
except:
    logDict = {
            "hardcoded": True,
            "version": 1,
            "formatters": {
                "sl1fw": {
                    "format": "%(levelname)s - %(name)s - %(message)s"
                    }
                },
            "handlers": {
                "journald": {
                    "class": "systemd.journal.JournalHandler",
                    "formatter": "sl1fw",
                    "SYSLOG_IDENTIFIER": "SL1FW"
                    }
                },
            "root": {
                "level": "INFO",
                "handlers": ["journald"]
                }
            }
#endtry

dictConfig(logDict)
logger = logging.getLogger()

if logDict.get("hardcoded", False):
    logger.warning("Failed to load logger settings, using hardcoded variant")
#endif

langs = dict()

for lang in ('cs', 'de', 'fr', 'it', 'es', 'pl'):
    try:
        langs[lang] = gettext.translation('sl1fw', localedir=defines.localedir, languages=[lang])
    except:
        logger.warning("Translation file for language %s not found.", lang)
    #endtry
#enddef

logger.info("Avaiable translations: %s", ", ".join(langs.keys()))

# use system locale settings
gettext.install('sl1fw', defines.localedir)
builtins.N_ = lambda x: x

from sl1fw import libPrinter

printer = libPrinter.Printer()
printer.run()
