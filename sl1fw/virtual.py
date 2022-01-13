#!/usr/bin/env python

# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

"""
This module is used to run a virtual printer. Virtual printer encompasses some of the real printer and parts of the
integration test mocks. All in all this launches the printer (similar to the one launched by main.py) that can run on
a desktop computer without motion controller connected. This mode is intended for GUI testing.
"""

import asyncio
import builtins
import concurrent
import gettext
import logging
import os
import signal
import tempfile
import threading
import warnings
from pathlib import Path
from shutil import copyfile
from unittest.mock import patch, Mock, AsyncMock

import pydbus
from gi.repository import GLib

import sl1fw.tests.mocks.mc_port
from sl1fw.api.factorytests0 import FactoryTests0
from sl1fw.hardware.printer_model import PrinterModel
from sl1fw.tests.mocks.exposure_screen import ExposureScreen
from sl1fw import defines, test_runtime
from sl1fw import libPrinter
from sl1fw.admin.manager import AdminManager
from sl1fw.api.admin0 import Admin0
from sl1fw.api.printer0 import Printer0
from sl1fw.api.standard0 import Standard0
from sl1fw.tests import samples
from sl1fw.tests.mocks.dbus.rauc import Rauc

# use system locale settings for translation
gettext.install("sl1fw", defines.localedir, names=("ngettext",))
builtins.N_ = lambda x: x  # type: ignore

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(name)s - %(message)s", level=logging.DEBUG)


# Display warnings only once
warnings.simplefilter("once")

temp_dir_obj = tempfile.TemporaryDirectory()
TEMP_DIR = Path(temp_dir_obj.name)
SAMPLES_DIR = Path(samples.__file__).parent
SL1FW_DIR = Path(sl1fw.__file__).parent
HARDWARE_FILE = TEMP_DIR / "sl1fw.hardware.cfg"
copyfile(SAMPLES_DIR / "hardware-virtual.cfg", HARDWARE_FILE)
HARDWARE_FILE_FACTORY = TEMP_DIR / "sl1fw.hardware.cfg.factory"
copyfile(SAMPLES_DIR / "hardware.toml", HARDWARE_FILE_FACTORY)

defines.expoPanelLogPath = TEMP_DIR / defines.expoPanelLogFileName
copyfile(SAMPLES_DIR / defines.expoPanelLogFileName, defines.expoPanelLogPath)


def change_dir(path):
    return os.path.join(defines.previousPrints, os.path.basename(path))


defines.hwConfigPath = HARDWARE_FILE
defines.factoryConfigPath = SL1FW_DIR / ".." / "factory" / "factory.toml"
defines.hwConfigPathFactory = HARDWARE_FILE_FACTORY
defines.templates = str(SL1FW_DIR / "intranet" / "templates")
test_runtime.testing = True
defines.cpuSNFile = str(SAMPLES_DIR / "nvmem")
defines.cpuTempFile = str(SAMPLES_DIR / "cputemp")
defines.multimediaRootPath = str(SL1FW_DIR / "multimedia")
defines.internalProjectPath = str(SAMPLES_DIR)
defines.ramdiskPath = str(TEMP_DIR)
defines.octoprintAuthFile = SAMPLES_DIR / "slicer-upload-api.key"
defines.livePreviewImage = str(Path(defines.ramdiskPath) / "live.png")
defines.displayUsageData = str(Path(defines.ramdiskPath) / "display_usage.npz")
defines.serviceData = str(Path(defines.ramdiskPath) / "service.toml")
defines.statsData = str(Path(defines.ramdiskPath) / "stats.toml")
defines.fan_check_override = True
defines.mediaRootPath = str(SAMPLES_DIR)
prev_prints = TEMP_DIR / "previous_prints"
prev_prints.mkdir(exist_ok=True)
defines.previousPrints = str(prev_prints)
defines.lastProjectHwConfig = change_dir(defines.lastProjectHwConfig)
defines.lastProjectFactoryFile = change_dir(defines.lastProjectFactoryFile)
defines.lastProjectConfigFile = change_dir(defines.lastProjectConfigFile)
defines.lastProjectPickler = change_dir(defines.lastProjectPickler)
defines.uvCalibDataPath = Path(defines.ramdiskPath) / defines.uvCalibDataFilename
defines.slicerProfilesFile = TEMP_DIR / defines.profilesFile
defines.loggingConfig = TEMP_DIR / "logging_config.json"
defines.last_job = Path(defines.ramdiskPath) / "last_job"
defines.last_log_token = Path(defines.ramdiskPath) / "last_log_token"
defines.printer_summary = Path(defines.ramdiskPath) / "printer_summary"
defines.firmwareListTemp = str(Path(defines.ramdiskPath) / "updates.json")
defines.slicerProfilesFile = Path(defines.ramdiskPath) / "slicer_profiles.toml"
defines.firmwareTempFile = str(Path(defines.ramdiskPath) / "update.raucb")
defines.emmc_serial_path = SAMPLES_DIR / "cid"
defines.factoryMountPoint = TEMP_DIR
defines.wizardHistoryPath = TEMP_DIR / "wizard_history" / "user_data"
defines.wizardHistoryPath.mkdir(exist_ok=True, parents=True)
defines.wizardHistoryPathFactory = TEMP_DIR / "wizard_history" / "factory_data"
defines.wizardHistoryPathFactory.mkdir(exist_ok=True, parents=True)
defines.uvCalibDataPathFactory = TEMP_DIR / "uv_calib_data_factory.toml"
defines.counterLog = TEMP_DIR / defines.counterLogFilename
defines.printer_model = TEMP_DIR / "model"
defines.sl1_model_file = defines.printer_model / "sl1"
defines.sl1s_model_file = defines.printer_model / "sl1s"
defines.detect_sla_model_file = TEMP_DIR / "detect-sla-model"
defines.printer_model.mkdir()
defines.sl1_model_file.touch()  # Set SL1 as the current model


class Virtual:
    def __init__(self):
        self.printer = None
        self.rauc_mocks = None
        self.glib_loop = None
        self.printer0 = None
        self.standard0 = None
        self.admin_manager = None
        self.admin0_dbus = None

    def __call__(self):
        signal.signal(signal.SIGINT, self.tear_down)
        signal.signal(signal.SIGTERM, self.tear_down)

        with patch("sl1fw.motion_controller.controller.serial", sl1fw.tests.mocks.mc_port), patch(
            "sl1fw.libUvLedMeterMulti.serial", sl1fw.tests.mocks.mc_port
        ), patch("sl1fw.motion_controller.controller.UInput", Mock()), patch(
            "sl1fw.motion_controller.controller.gpio", Mock()
        ), patch(
            "sl1fw.functions.files.get_save_path", self.fake_save_path
        ), patch(
            "sl1fw.libHardware.ExposureScreen", ExposureScreen
        ), patch(
            "sl1fw.libHardware.Hardware.isCoverClosed", Mock(return_value=True)
        ), patch(
            # fake resin measurement 100 ml
            "sl1fw.libHardware.Hardware.get_resin_volume_async", AsyncMock(return_value=100)
        ):
            print("Resolving system bus")
            bus = pydbus.SystemBus()
            print("Publishing Rauc mock")
            self.rauc_mocks = bus.publish(Rauc.__OBJECT__, ("/", Rauc()))

            print("Initializing printer")
            self.printer = libPrinter.Printer()

            test_runtime.exposure_image = self.printer.exposure_image
            self.printer.hw.printer_model = PrinterModel.SL1

            print("Overriding printer settings")
            self.printer.hw.config.calibrated = True
            self.printer.hw.config.fanCheck = False
            self.printer.hw.config.coverCheck = False
            self.printer.hw.config.resinSensor = True

            print("Publishing printer on D-Bus")
            self.printer0 = bus.publish(Printer0.__INTERFACE__, Printer0(self.printer))
            self.standard0 = bus.publish(Standard0.__INTERFACE__, Standard0(self.printer))
            self.admin_manager = AdminManager()
            self.admin0_dbus = bus.publish(Admin0.__INTERFACE__, Admin0(self.admin_manager, self.printer))
            FactoryTests0(self.printer)
            print("Running printer")
            threading.Thread(target=self.printer.setup).start()  # Does not block, but requires Rauc on DBus
            print("Running glib mainloop")
            self.glib_loop = GLib.MainLoop().run()
            self.glib_loop.run()  # type: ignore[attr-defined]
            print("Unpublishing Rauc mock")
            self.rauc_mocks.unpublish()

    def tear_down(self, signum, _):
        if signum != signal.SIGTERM:
            return

        print("Running virtual printer tear down")
        asyncio.run(self.async_tear_down())
        print("Virtual printer teardown finished")

    @staticmethod
    def fake_save_path():
        return Path(TEMP_DIR)

    async def async_tear_down(self):
        loop = asyncio.get_running_loop()
        # Run all teardown parts in parallel. Some may block or fail
        with concurrent.futures.ThreadPoolExecutor() as pool:
            tasks = [
                loop.run_in_executor(pool, self.printer.stop),
                loop.run_in_executor(pool, self.rauc_mocks.unpublish),
                loop.run_in_executor(pool, self.glib_loop.quit),
                loop.run_in_executor(pool, self.printer0.unpublish),
                loop.run_in_executor(pool, self.standard0.unpublish),
                loop.run_in_executor(pool, self.admin0_dbus.unpublish),
            ]
        await asyncio.gather(*tasks)


def run_virtual():
    Virtual()()


if __name__ == "__main__":
    run_virtual()
