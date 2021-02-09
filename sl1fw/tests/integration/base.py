# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import shutil
import weakref

from pathlib import Path
from queue import Empty
from shutil import copyfile
from threading import Thread

# import cProfile
from typing import Optional
from tempfile import TemporaryDirectory

from pydbus import SystemBus

from sl1fw.tests.base import Sl1fwTestCase
from sl1fw import defines, test_runtime
from sl1fw.api.printer0 import Printer0
from sl1fw.libPrinter import Printer
from sl1fw.tests.mocks.display import TestDisplay


class Sl1FwIntegrationTestCaseBase(Sl1fwTestCase):
    # pylint: disable = too-many-instance-attributes
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.display = TestDisplay()
        self.printer: Optional[Printer] = None
        self.thread: Optional[Thread] = None
        self.temp_dir_project = None

    def setUp(self):
        super().setUp()

        self.hardware_file = self.TEMP_DIR / "sl1fw.hardware.cfg"
        self.sdl_audio_file = self.TEMP_DIR / "sl1fw.sdl_audio.raw"
        self.api_key_file = self.TEMP_DIR / "api.key"
        self.uv_calib_data_file = self.TEMP_DIR / defines.uvCalibDataFilename
        self.uv_calib_factory_data_file = (
            self.TEMP_DIR / f"factory-{defines.uvCalibDataFilename}"
        )
        self.counter_log = self.TEMP_DIR / defines.counterLogFilename
        self.wizard_data_file = self.TEMP_DIR / defines.wizardDataFilename
        self.factory_config_file = self.TEMP_DIR / "factory.toml"
        self.hardwarwe_factory_file = self.TEMP_DIR / "hardware.toml"

        print(f"<<<<<===== {self.id()} =====>>>>>")
        copyfile(self.SAMPLES_DIR / "hardware.cfg", self.hardware_file)
        copyfile(
            self.SL1FW_DIR / ".." / "factory" / "factory.toml", self.factory_config_file
        )
        copyfile(self.SAMPLES_DIR / "hardware.toml", self.hardwarwe_factory_file)
        self.temp_dir_project = TemporaryDirectory()
        self.temp_dir_wizard_history = TemporaryDirectory()

        self.rewriteDefines()

        Path(self.api_key_file).touch()
        Path(self.uv_calib_data_file).touch()
        shutil.copy(self.SAMPLES_DIR / "self_test_data.json", Path(defines.factoryMountPoint))
        shutil.copy(
            self.SAMPLES_DIR / "uvcalib_data-60.toml",
            Path(self.uv_calib_factory_data_file),
        )

        os.environ["SDL_AUDIODRIVER"] = "disk"
        os.environ["SDL_DISKAUDIOFILE"] = str(self.sdl_audio_file)

        self.printer = Printer(debug_display=self.display)
        test_runtime.screen = self.printer.screen

        # overide writeToFactory function
        self.printer.display.pages["factoryreset"].writeToFactory = self.call

        self._printer0 = Printer0(self.printer)
        # pylint: disable = no-member
        self.printer0_dbus = SystemBus().publish(
            Printer0.__INTERFACE__,
            (None, weakref.proxy(self._printer0), self._printer0.dbus),
        )
        self.thread = Thread(target=self.printer_thread)

        self.tryStartPrinter()

    def rewriteDefines(self) -> None:
        defines.wizardHistoryPath = Path(self.temp_dir_wizard_history.name)
        defines.cpuSNFile = str(self.SAMPLES_DIR / "nvmem")
        defines.cpuTempFile = str(self.SAMPLES_DIR / "cputemp")
        defines.factoryConfigPath = str(self.factory_config_file)
        defines.hwConfigPathFactory = self.hardwarwe_factory_file
        defines.templates = str(self.SL1FW_DIR / "intranet" / "templates")
        defines.multimediaRootPath = str(self.SL1FW_DIR / "multimedia")
        defines.hwConfigPath = self.hardware_file
        defines.truePoweroff = False
        defines.internalProjectPath = str(self.SAMPLES_DIR)
        defines.octoprintAuthFile = str(self.SAMPLES_DIR / "slicer-upload-api.key")
        defines.livePreviewImage = str(Path(defines.ramdiskPath) / "live.png")
        defines.displayUsageData = str(Path(defines.ramdiskPath) / "display_usage.npz")
        defines.serviceData = str(Path(defines.ramdiskPath) / "service.toml")
        defines.statsData = str(Path(defines.ramdiskPath) / "stats.toml")
        defines.fan_check_override = True
        defines.loggingConfig = self.TEMP_DIR / "logger_config.json"

        defines.previousPrints = self.temp_dir_project.name
        defines.lastProjectHwConfig = self._change_dir(defines.lastProjectHwConfig)
        defines.lastProjectFactoryFile = self._change_dir(
            defines.lastProjectFactoryFile
        )
        defines.lastProjectConfigFile = self._change_dir(defines.lastProjectConfigFile)
        defines.lastProjectPickler = self._change_dir(defines.lastProjectPickler)

        defines.last_job = Path(defines.ramdiskPath) / "last_job"
        defines.last_log_token = Path(defines.ramdiskPath) / "last_log_token"

        # factory reset
        defines.apikeyFile = str(self.api_key_file)
        defines.uvCalibDataPath = self.uv_calib_data_file
        defines.uvCalibDataPathFactory = self.uv_calib_factory_data_file
        defines.counterLog = self.counter_log
        defines.wizardDataPathFactory = str(self.wizard_data_file)

    def _change_dir(self, path) -> str:
        return self.temp_dir_project.name + "/" + os.path.basename(path)

    def tryStartPrinter(self):
        try:
            self.thread.start()

            # Skip wizard
            self.waitPage("confirm", timeout_sec=10)
            self.press("back")
            self.waitPage("yesno")
            self.press("yes")
            # Skip calibration
            self.waitPage("confirm")
            self.press("back")
            self.waitPage("yesno")
            self.press("yes")
            self.waitPage("home")
        except Exception as exception:
            self.tearDown()
            raise Exception("Test setup failed") from exception

    def printer_thread(self):
        self.printer.run()
        # cProfile.runctx('self.printer.start()', globals=globals(), locals=locals())

    def tearDown(self):
        self.printer0_dbus.unpublish()
        print(Printer0.PropertiesChanged.map)
        if self._printer0 in Printer0.PropertiesChanged.map:
            del Printer0.PropertiesChanged.map[self._printer0]

        self.printer.exit()
        self.thread.join()

        # Make sure we are not leaving these behind.
        # Base test tear down checks this does not happen.
        del self.printer
        del self._printer0
        del self.printer0_dbus
        test_runtime.screen = None

        files = [
            self.EEPROM_FILE,
            self.hardware_file,
            self.sdl_audio_file,
            self.api_key_file,
            self.uv_calib_data_file,
            self.factory_config_file,
        ]

        for file in files:
            if file.exists():
                file.unlink()

        self.temp_dir_project.cleanup()
        self.temp_dir_wizard_history.cleanup()
        print(f"<<<<<===== {self.id()} =====>>>>>")
        super().tearDown()  # closes logger!

    def press(self, identifier, data=None):
        print("Pressing button: %s on page %s" % (identifier, self.display.page))
        self.display.add_event(self.display.page, identifier, pressed=True, data=data)
        self.display.add_event(self.display.page, identifier, pressed=False, data=data)

    def waitPage(self, page: str, timeout_sec: int = 5):
        try:
            self.assertEqual(page, self.display.read_page(timeout_sec=timeout_sec))
        except Empty as exception:
            raise Exception(
                f'Wait timeout for page "{page}" ({timeout_sec} seconds)'
            ) from exception
        print("Wait done for: %s" % page)

    def readItems(self):
        return self.display.read_items(timeout_sec=3)

    def switchPage(self, page):
        self.press(page)
        self.waitPage(page)

    @staticmethod
    def call(fce):
        fce()
