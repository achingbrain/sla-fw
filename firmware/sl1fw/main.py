#!/usr/bin/env python

# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# TODO: Fix following pylint problems
# pylint: disable=wrong-import-position

import builtins
import gettext
import logging
import warnings
from threading import Thread

from gi.repository import GLib
from pydbus import SystemBus

from sl1fw import defines
from sl1fw.api.printer0 import Printer0
from sl1fw.logger_config import configure_log

log_from_config = configure_log()
logger = logging.getLogger()

if log_from_config:
    logger.info("Logging configuration read from configuration file")
else:
    logger.info("Embedded logger configuration was used")

logger.info("Logging is set to level %s", logging.getLevelName(logger.level))

# use system locale settings for translation
gettext.install("sl1fw", defines.localedir, names=("ngettext"))
builtins.N_ = lambda x: x

from sl1fw import libPrinter

warnings.simplefilter("ignore")

def event_thread():
    logger.info("Starting printer event loop")
    GLib.MainLoop().run()
    logger.info("Printer event loop exited")


printer = libPrinter.Printer()
Thread(target=event_thread, daemon=True).start()
SystemBus().publish(Printer0.__INTERFACE__, Printer0(printer))
printer.run()
