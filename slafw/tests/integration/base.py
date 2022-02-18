# This file is part of the SLA firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import shutil
import weakref

from pathlib import Path
from shutil import copyfile
from threading import Thread

# import cProfile
from typing import Optional
from tempfile import TemporaryDirectory

from pydbus import SystemBus

from slafw.tests.base import SlafwTestCaseDBus, RefCheckTestCase
from slafw import defines, test_runtime
from slafw.api.printer0 import Printer0
from slafw.libPrinter import Printer


class SlaFwIntegrationTestCaseBase(SlafwTestCaseDBus, RefCheckTestCase):
    # pylint: disable = too-many-instance-attributes
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.printer: Optional[Printer] = None
        self.thread: Optional[Thread] = None
        self.temp_dir_project = None

    def setUp(self):
        super().setUp()

        self.hardware_file = self.TEMP_DIR / "slafw.hardware.cfg"
        self.sdl_audio_file = self.TEMP_DIR / "slafw.sdl_audio.raw"
        self.api_key_file = self.TEMP_DIR / "api.key"
        self.uv_calib_data_file = self.TEMP_DIR / defines.uvCalibDataFilename
        self.uv_calib_factory_data_file = (
            self.TEMP_DIR / f"factory-{defines.uvCalibDataFilename}"
        )
        self.counter_log = self.TEMP_DIR / defines.counterLogFilename
        self.wizard_data_file = self.TEMP_DIR / defines.wizardDataFilename
        self.hardwarwe_factory_file = self.TEMP_DIR / "hardware.toml"

        print(f"<<<<<===== {self.id()} =====>>>>>")
        copyfile(self.SAMPLES_DIR / "hardware.cfg", self.hardware_file)
        copyfile(self.SAMPLES_DIR / "hardware.toml", self.hardwarwe_factory_file)
        self.temp_dir_project = TemporaryDirectory()
        self.temp_dir_wizard_history = TemporaryDirectory()

        self.rewriteDefines()

        Path(self.api_key_file).touch()
        defines.nginx_http_digest.touch()
        Path(self.uv_calib_data_file).touch()
        shutil.copy(self.SAMPLES_DIR / "self_test_data.json", Path(defines.factoryMountPoint))
        shutil.copy(
            self.SAMPLES_DIR / "uvcalib_data-60.toml",
            Path(self.uv_calib_factory_data_file),
        )

        os.environ["SDL_AUDIODRIVER"] = "disk"
        os.environ["SDL_DISKAUDIOFILE"] = str(self.sdl_audio_file)

        self.printer = Printer()
        test_runtime.exposure_image = self.printer.exposure_image

        self._printer0 = Printer0(self.printer)
        # pylint: disable = no-member
        self.printer0_dbus = SystemBus().publish(
            Printer0.__INTERFACE__,
            (None, weakref.proxy(self._printer0), self._printer0.dbus),
        )
        self.try_start_printer()

    def rewriteDefines(self) -> None:
        defines.wizardHistoryPath = Path(self.temp_dir_wizard_history.name)
        defines.cpuSNFile = str(self.SAMPLES_DIR / "nvmem")
        defines.cpuTempFile = str(self.SAMPLES_DIR / "cputemp")
        defines.hwConfigPathFactory = self.hardwarwe_factory_file
        defines.templates = str(self.SLAFW_DIR / "intranet" / "templates")
        defines.hwConfigPath = self.hardware_file
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
        defines.uvCalibDataPath = self.uv_calib_data_file
        defines.uvCalibDataPathFactory = self.uv_calib_factory_data_file
        defines.counterLog = self.counter_log
        defines.wizardDataPathFactory = str(self.wizard_data_file)

        defines.nginx_http_digest = self.TEMP_DIR / "http_digest_enabled"

    def _change_dir(self, path) -> str:
        return self.temp_dir_project.name + "/" + os.path.basename(path)

    def try_start_printer(self):
        try:
            self.printer.setup()
            # cProfile.runctx('self.printer.start()', globals=globals(), locals=locals())
        except Exception as exception:
            self.tearDown()
            raise Exception("Test setup failed") from exception

    def tearDown(self):
        self.printer0_dbus.unpublish()
        # This fixes symptoms of a bug in pydbus. Drop circular dependencies.
        if self._printer0 in Printer0.PropertiesChanged.map:  # pylint: disable = no-member
            del Printer0.PropertiesChanged.map[self._printer0]  # pylint: disable = no-member
        if self._printer0 in Printer0.exception.map:  # pylint: disable = no-member
            del Printer0.exception.map[self._printer0]  # pylint: disable = no-member

        self.printer.stop()

        # Make sure we are not leaving these behind.
        # Base test tear down checks this does not happen.
        del self.printer
        del self._printer0
        del self.printer0_dbus
        test_runtime.exposure_image = None

        files = [
            self.EEPROM_FILE,
            self.hardware_file,
            self.sdl_audio_file,
            self.api_key_file,
            self.uv_calib_data_file,
        ]

        for file in files:
            if file.exists():
                file.unlink()

        self.temp_dir_project.cleanup()
        self.temp_dir_wizard_history.cleanup()
        print(f"<<<<<===== {self.id()} =====>>>>>")
        super().tearDown()  # closes logger!

    @staticmethod
    def call(fce):
        fce()
