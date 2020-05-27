#!/usr/bin/env python

# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

"""
This module is used to run a virtual printer. Virtual printer encompasses some of the real printer and parts of the
integration test mocks. All in all this launches the printer (similar to the one launched by main.py) that can run on
a desktop computer without motion controller connected. This mode is intended for GUI testing.
"""

import builtins
import gettext
import logging
import os
import tempfile
import warnings
from pathlib import Path
from shutil import copyfile
from threading import Thread

import pydbus
from gi.repository import GLib
from mock import Mock, patch

import sl1fw.tests.mocks.mc_port
from sl1fw import defines
from sl1fw import libPrinter
from sl1fw.api.printer0 import Printer0
from sl1fw.tests import samples
from sl1fw.tests.mocks.dbus.rauc import Rauc

# use system locale settings for translation
gettext.install("sl1fw", defines.localedir, names=("ngettext",))
builtins.N_ = lambda x: x

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s", level=logging.DEBUG
)

# Display warnings only once
warnings.simplefilter("once")

TEMP_DIR = Path(tempfile.gettempdir())
SAMPLES_DIR = Path(samples.__file__).parent
SL1FW_DIR = Path(sl1fw.__file__).parent
HARDWARE_FILE = TEMP_DIR / "sl1fw.hardware.cfg"
copyfile(SAMPLES_DIR / "hardware-virtual.cfg", HARDWARE_FILE)

defines.hwConfigFile = HARDWARE_FILE
defines.factoryConfigFile = str(SL1FW_DIR / ".." / "factory" / "factory.toml")
defines.hwConfigFactoryDefaultsFile = str(SAMPLES_DIR / "hardware.toml")
defines.templates = str(SL1FW_DIR / "intranet" / "templates")
defines.testing = True
defines.truePoweroff = False
defines.fbFile = "/dev/null"
defines.cpuSNFile = str(SAMPLES_DIR / "nvmem")
defines.cpuTempFile = str(SAMPLES_DIR / "cputemp")
defines.multimediaRootPath = str(SL1FW_DIR / "multimedia")
defines.internalProjectPath = str(SAMPLES_DIR)
defines.ramdiskPath = tempfile.gettempdir()
defines.octoprintAuthFile = str(SAMPLES_DIR / "slicer-upload-api.key")
defines.livePreviewImage = str(Path(defines.ramdiskPath) / "live.png")
defines.displayUsageData = str(Path(defines.ramdiskPath) / "display_usage.npz")
defines.serviceData = str(Path(defines.ramdiskPath) / "service.toml")
defines.statsData = str(Path(defines.ramdiskPath) / "stats.toml")
defines.fan_check_override = True
defines.mediaRootPath = str(SAMPLES_DIR)
defines.temp_previousPrints = tempfile.TemporaryDirectory()
defines.previousPrints = defines.temp_previousPrints.name
change_dir = lambda x : os.path.join(defines.previousPrints, os.path.basename(x))
defines.lastProjectHwConfig = change_dir(defines.lastProjectHwConfig)
defines.lastProjectFactoryFile = change_dir(defines.lastProjectFactoryFile)
defines.lastProjectConfigFile = change_dir(defines.lastProjectConfigFile)
defines.lastProjectPickler = change_dir(defines.lastProjectPickler)

with patch(
    "sl1fw.motion_controller.controller.serial", sl1fw.tests.mocks.mc_port
), patch("sl1fw.motion_controller.controller.UInput", Mock()), patch(
    "sl1fw.motion_controller.controller.gpio", Mock()
), patch(
    "serial.tools.list_ports", Mock()
):
    bus = pydbus.SystemBus()
    rauc_mocks = bus.publish(Rauc.__OBJECT__, ("/", Rauc()))

    Thread(target=GLib.MainLoop().run, daemon=True).start()

    printer = libPrinter.Printer()

    printer.hwConfig.calibrated = True
    printer.hwConfig.fanCheck = False
    printer.hwConfig.coverCheck = False
    printer.hwConfig.resinSensor = False

    bus.publish(Printer0.__INTERFACE__, Printer0(printer))
    printer.run()

    rauc_mocks.unpublish()
