# This file is part of the SLA firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import gc
import importlib
import logging
import os
import sys
import tempfile
import threading
import warnings
import weakref
from pathlib import Path
from types import FrameType
from unittest import TestCase
from unittest.mock import Mock, patch

import pydbus
from PIL import Image, ImageChops
from dbusmock import DBusTestCase
from gi.repository import GLib

import slafw.tests.mocks.exposure_screen
import slafw.tests.mocks.mc_port as mc_port
import slafw.tests.mocks.sl1s_uvled_booster
from slafw import defines, test_runtime
from slafw.api.exposure0 import Exposure0
from slafw.api.printer0 import Printer0
from slafw.api.wizard0 import Wizard0
from slafw.exposure.exposure import Exposure
from slafw.functions.system import set_configured_printer_model
from slafw.hardware.printer_model import PrinterModel
from slafw.image.exposure_image import ExposureImage
from slafw.libPrinter import Printer
from slafw.tests import samples
from slafw.tests.mocks.dbus.filemanager0 import FileManager0
from slafw.tests.mocks.dbus.hostname import Hostname
from slafw.tests.mocks.dbus.locale import Locale
from slafw.tests.mocks.dbus.networkmanager import NetworkManager
from slafw.tests.mocks.dbus.rauc import Rauc
from slafw.tests.mocks.dbus.systemd import Systemd
from slafw.tests.mocks.dbus.timedate import TimeDate
from slafw.tests.mocks.gettext import fake_gettext
from slafw.wizard.wizard import Wizard


class SlafwTestCase(TestCase):
    # pylint: disable = too-many-instance-attributes
    LOGGER_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"

    LOGGER_STREAM_HANDLER_NAME = "sla-fw custom stream handler"

    SLAFW_DIR = Path(slafw.__file__).parent
    SAMPLES_DIR = Path(samples.__file__).parent
    EEPROM_FILE = Path.cwd() / "EEPROM.dat"

    patches = [
        patch("slafw.motion_controller.controller.gpio"),
        patch("slafw.motion_controller.controller.UInput"),
        patch("slafw.motion_controller.controller.serial", mc_port),
        patch("slafw.libUvLedMeterMulti.serial.tools.list_ports"),
        patch("slafw.hardware.base.hardware.ExposureScreen", slafw.tests.mocks.exposure_screen.ExposureScreen),
        patch("slafw.hardware.hardware_sl1.Booster", slafw.tests.mocks.sl1s_uvled_booster.BoosterMock)
    ]

    def setUp(self) -> None:
        fake_gettext()
        for p in self.patches:
            p.start()

        # Make sure we use unmodified defines
        importlib.reload(defines)

        # Set stream handler here in order to use stdout already captured by unittest
        self.stream_handler = logging.StreamHandler(sys.stdout)
        self.stream_handler.name = self.LOGGER_STREAM_HANDLER_NAME
        self.stream_handler.setFormatter(logging.Formatter(self.LOGGER_FORMAT))
        logger = logging.getLogger()
        if any([handler.name == self.LOGGER_STREAM_HANDLER_NAME for handler in logger.handlers]):
            raise RuntimeError("Handler already installed !!! Failed to run super().tearDown in previous test ???")
        logger.handlers.clear()  # remove handlers which might be present from imported modules. For example gpio.py
        logger.addHandler(self.stream_handler)
        logger.setLevel(logging.DEBUG)

        # gitlab CI job creates model folder in different location due to restricted permissions in Docker container
        # common path is /builds/project-0/model
        if "CI" in os.environ:
            defines.printer_model_run = Path(os.environ["CI_PROJECT_DIR"] + "/model")
        printer_model = PrinterModel()

        # Test overrides
        warnings.simplefilter("always")
        test_runtime.testing = True

        # Test temp paths
        self.temp_dir_obj = tempfile.TemporaryDirectory()
        self.TEMP_DIR = Path(self.temp_dir_obj.name)
        defines.ramdiskPath = str(self.TEMP_DIR)
        defines.previousPrints = str(self.TEMP_DIR)
        defines.emmc_serial_path = self.SAMPLES_DIR / "cid"
        defines.wizardHistoryPath = self.TEMP_DIR / "wizard_history" / "user_data"
        defines.wizardHistoryPath.mkdir(exist_ok=True, parents=True)
        defines.wizardHistoryPathFactory = self.TEMP_DIR / "wizard_history" / "factory_data"
        defines.wizardHistoryPathFactory.mkdir(exist_ok=True, parents=True)
        defines.factoryMountPoint = self.TEMP_DIR
        defines.configDir = self.TEMP_DIR
        defines.uvCalibDataPathFactory = self.TEMP_DIR / defines.uvCalibDataFilename
        defines.wizardDataPathFactory = self.TEMP_DIR / defines.wizardDataFilename
        defines.hwConfigPath = self.TEMP_DIR / "hwconfig.toml"
        defines.hwConfigPathFactory = self.TEMP_DIR / "hwconfig-factory.toml"
        defines.printer_model = self.TEMP_DIR / "model"
        set_configured_printer_model(printer_model)  # Do not run UpgradeWizard by default
        defines.firstboot = self.TEMP_DIR / "firstboot"
        defines.expoPanelLogPath = self.TEMP_DIR / defines.expoPanelLogFileName
        defines.factory_enable = self.TEMP_DIR / "factory_mode_enabled"
        defines.factory_enable.touch()  # Enable factory mode
        defines.exposure_panel_of_node = self.SAMPLES_DIR / "of_node" / printer_model.name.lower()
        defines.cpuSNFile = self.SAMPLES_DIR / "nvmem"

    def assertSameImage(self, a: Image, b: Image, threshold: int = 0, msg=None):
        if a.mode != b.mode:
            a = a.convert(b.mode)
        diff = ImageChops.difference(a, b).convert(mode="L")
        thres = diff.point(lambda x: 1 if x > threshold else 0, mode="L")
        if thres.getbbox():
            msg = self._formatMessage(
                msg, f"Images contain pixels different by mote than {threshold}."
            )
            a.save("assertSameImage-a.png")
            b.save("assertSameImage-b.png")
            raise self.failureException(msg)

    def tearDown(self) -> None:
        logging.getLogger().removeHandler(self.stream_handler)
        self.temp_dir_obj.cleanup()

        for p in self.patches:
            p.stop()

        super().tearDown()


class RefCheckTestCase(TestCase):
    def tearDown(self) -> None:
        gc.collect()
        self.ref_check_type(Printer0)
        self.ref_check_type(Printer)
        self.ref_check_type(Exposure0)
        self.ref_check_type(Exposure)
        self.ref_check_type(Wizard0)
        self.ref_check_type(Wizard)
        self.ref_check_type(ExposureImage)

        super().tearDown()

    def ref_check_type(self, t: type):
        instances = 0
        for obj in gc.get_objects():
            try:
                if isinstance(obj, (weakref.ProxyTypes, Mock)):
                    continue
                if isinstance(obj, t):
                    print(f"Referrers to {t}:")
                    for num, ref in enumerate(gc.get_referrers(obj)):
                        # do NOT count "global" and "class 'frame'" referrers
                        if isinstance(ref, FrameType):
                            print(f"Not counted 'frame' referrer {num}: {ref}")
                        elif isinstance(ref, list) and len(ref) > 100:
                            print(f"Not counted 'global' referrer {num}: <100+ LONG LIST>")
                        else:
                            instances += 1
                            print(f"Referrer {num}: {ref} - {type(ref)}")
            except ReferenceError:
                # Weak reference no longer valid
                pass
        self.assertEqual(0, instances, f"Found {instances} of {t} left behind by test run")


class SlafwTestCaseDBus(SlafwTestCase, DBusTestCase):
    dbus_started = False
    dbus_mocks = []
    event_loop = GLib.MainLoop()
    event_thread: threading.Thread = None

    @classmethod
    def setUpClass(cls):
        DBusTestCase.setUpClass()
        if not cls.dbus_started:
            cls.start_system_bus()
            cls.dbus_started = True

        cls.event_thread = threading.Thread(target=cls.event_loop.run)
        cls.event_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.event_loop.quit()
        cls.event_thread.join()
        # TODO: Would be nice to properly terminate fake dbus bus and start new one next time
        #       Unfortunately this does not work out of the box.
        # DBusTestCase.tearDownClass()

    def setUp(self) -> None:
        super().setUp()

        # DBus mocks
        nm = NetworkManager()
        bus = pydbus.SystemBus()
        self.hostname = Hostname()
        self.locale = Locale()
        self.time_date = TimeDate()
        self.systemd = Systemd()
        self.dbus_mocks = [
            bus.publish(
                NetworkManager.__INTERFACE__,
                nm,
                ("Settings", nm),
                ("ethernet", nm),
                ("wifi0", nm),
                ("wifi1", nm),
            ),
            bus.publish(FileManager0.__INTERFACE__, FileManager0()),
            bus.publish(Hostname.__INTERFACE__, self.hostname),
            bus.publish(Rauc.__OBJECT__, ("/", Rauc())),
            bus.publish(Locale.__INTERFACE__, self.locale),
            bus.publish(TimeDate.__INTERFACE__, self.time_date),
            bus.publish(Systemd.__INTERFACE__, self.systemd)
        ]

    def tearDown(self) -> None:
        for dbus_mock in self.dbus_mocks:
            dbus_mock.unpublish()

        super().tearDown()
