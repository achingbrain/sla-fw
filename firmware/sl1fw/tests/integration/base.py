# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from queue import Empty
from pathlib import Path
import os
from threading import Thread
from shutil import copyfile
# import cProfile
from typing import Optional

from sl1fw.tests.base import Sl1fwTestCase

from sl1fw.tests.mocks.display import TestDisplay
from sl1fw.libPrinter import Printer
from sl1fw import defines
from sl1fw.pages.printstart import PagePrintPreviewSwipe


class Sl1FwIntegrationTestCaseBase(Sl1fwTestCase):
    FB_DEV_FILE = Sl1fwTestCase.TEMP_DIR / "sl1fw.fb_dev.dat"
    HARDWARE_FILE = Sl1fwTestCase.TEMP_DIR / "sl1fw.hardware.cfg"
    SDL_AUDIO_FILE = Sl1fwTestCase.TEMP_DIR / "sl1fw.sdl_audio.raw"
    LAST_PROJECT_FILE = Sl1fwTestCase.TEMP_DIR / "last_project.toml"
    API_KEY_FILE = Sl1fwTestCase.TEMP_DIR / "api.key"
    UV_CALIB_DATA_FILE = Sl1fwTestCase.TEMP_DIR / defines.uvCalibDataFilename
    FACTORY_CONFIG_FILE = Sl1fwTestCase.TEMP_DIR / "factory.toml"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.display = TestDisplay()
        self.printer: Optional[Printer] = None
        self.thread: Optional[Thread] = None

    def setUp(self):
        super().setUp()
        copyfile(self.SAMPLES_DIR / "hardware.cfg", self.HARDWARE_FILE)
        copyfile(self.SL1FW_DIR / ".." / "factory" / "factory.toml", self.FACTORY_CONFIG_FILE)

        defines.cpuSNFile = str(self.SAMPLES_DIR / "nvmem")
        defines.cpuTempFile = str(self.SAMPLES_DIR / "cputemp")
        defines.factoryConfigFile = str(self.FACTORY_CONFIG_FILE)
        defines.hwConfigFactoryDefaultsFile = str(self.SAMPLES_DIR / "hardware.toml")
        defines.lastProjectData = str(self.LAST_PROJECT_FILE)
        defines.templates = str(self.SL1FW_DIR / "intranet" / "templates")
        defines.multimediaRootPath = str(self.SL1FW_DIR / "multimedia")
        defines.hwConfigFile = self.HARDWARE_FILE
        defines.fbFile = str(self.FB_DEV_FILE)
        defines.truePoweroff = False
        defines.internalProjectPath = str(self.SAMPLES_DIR)
        defines.octoprintAuthFile = str(self.SAMPLES_DIR / "slicer-upload-api.key")
        defines.livePreviewImage = str(Path(defines.ramdiskPath) / "live.png")
        defines.displayUsageData = str(Path(defines.ramdiskPath) / "display_usage.npz")
        defines.serviceData = str(Path(defines.ramdiskPath) / "service.toml")
        defines.statsData = str(Path(defines.ramdiskPath) / "stats.toml")

        # factory reset
        defines.apikeyFile = str(self.API_KEY_FILE)
        defines.uvCalibDataPath = str(self.UV_CALIB_DATA_FILE)
        Path(self.API_KEY_FILE).touch()
        Path(self.UV_CALIB_DATA_FILE).touch()

        os.environ['SDL_AUDIODRIVER'] = "disk"
        os.environ['SDL_DISKAUDIOFILE'] = str(self.SDL_AUDIO_FILE)

        PagePrintPreviewSwipe.FanCheckOverride = True

        self.printer = Printer(debugDisplay=self.display)
        # overide writeToFactory function
        self.printer.display.pages['factoryreset'].writeToFactory = self.call

        self.thread = Thread(target=self.printer_thread)

        try:
            self.thread.start()
            self.waitPage("splash")

            # Skip wizard
            self.waitPage("confirm")
            self.press("back")
            self.waitPage("yesno")
            self.press("yes")
            if os.path.isfile(defines.lastProjectData):
                self.waitPage("finished")
                self.press("home")
            self.waitPage("home")
        except Exception as exception:
            self.tearDown()
            raise exception

    def printer_thread(self):
        self.printer.run()
        # cProfile.runctx('self.printer.start()', globals=globals(), locals=locals())

    def tearDown(self):
        self.printer.exit()
        self.thread.join()

        files = [
            self.EEPROM_FILE,
            self.FB_DEV_FILE,
            self.HARDWARE_FILE,
            self.SDL_AUDIO_FILE,
            self.LAST_PROJECT_FILE,
            self.API_KEY_FILE,
            self.UV_CALIB_DATA_FILE,
            self.FACTORY_CONFIG_FILE,
        ]

        for file in files:
            if file.exists():
                file.unlink()

    def press(self, identifier, data=None):
        print("Pressing button: %s on page %s" % (identifier, self.display.page))
        self.display.add_event(self.display.page, identifier, pressed=True, data=data)
        self.display.add_event(self.display.page, identifier, pressed=False, data=data)

    def waitPage(self, page: str, timeout_sec: int = 3):
        try:
            self.assertEqual(page, self.display.read_page(timeout_sec=timeout_sec))
        except Empty as exception:
            raise Exception(f"Wait timeout for page \"{page}\" ({timeout_sec} seconds)") from exception
        print("Wait done for: %s" % page)

    def readItems(self):
        return self.display.read_items(timeout_sec=3)

    def switchPage(self, page):
        self.press(page)
        self.waitPage(page)

    def call(self, fce):
        fce()
