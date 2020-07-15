# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# TODO: Fix following pylint problems
# pylint: disable=too-many-statements
# pylint: disable=too-many-instance-attributes

import gettext
import logging
import os
import re
import threading
from pathlib import Path
from time import monotonic
from typing import Optional

import distro
import pydbus
from PySignal import Signal
from gi.repository import GLib
from pydbus import SystemBus
from prusaerrors.sl1.codes import Sl1Codes

from sl1fw import defines, test_runtime
from sl1fw.api.config0 import Config0
from sl1fw.api.display_test0 import DisplayTest0State
from sl1fw.errors.exceptions import ConfigException
from sl1fw.libAsync import AdminCheck
from sl1fw.libAsync import SlicerProfileUpdater
from sl1fw.libConfig import HwConfig, TomlConfig, RuntimeConfig
from sl1fw.libDisplay import Display
from sl1fw.libHardware import Hardware
from sl1fw.libHardware import MotConComState
from sl1fw.libNetwork import Network
from sl1fw.libQtDisplay import QtDisplay
from sl1fw.libScreen import Screen
from sl1fw.libExposure import Exposure
from sl1fw.logger_config import set_log_level
from sl1fw.pages.start import PageStart
from sl1fw.pages.wait import PageWait
from sl1fw.state_actions.manager import ActionManager
from sl1fw.slicer.slicer_profile import SlicerProfile
from sl1fw.states.printer import PrinterState
from sl1fw.states.unboxing import UnboxingState


class Printer:
    def __init__(self, debug_display=None):
        self.logger = logging.getLogger(__name__)
        init_time = monotonic()
        self.exception: Optional[Exception] = None
        self.start_time = None
        self.admin_check = None
        self.slicer_profile = None
        self.slicer_profile_updater = None
        self._state = PrinterState.INIT
        self.state_changed = Signal()
        self.firstRun = True
        self.action_manager = ActionManager()
        self.action_manager.exposure_change.connect(self._exposure_changed)
        self.action_manager.unboxing_change.connect(self._unboxing_changed)
        self.action_manager.display_test_change.connect(self._display_test_changed)
        self.exited = threading.Event()
        self.exited.set()
        self.logger.info("SL1 firmware initializing")

        self.logger.info("Initializing hwconfig")
        self.hwConfig = HwConfig(
            file_path=Path(defines.hwConfigPath),
            factory_file_path=Path(defines.hwConfigPathFactory),
            is_master=True,
        )
        self.runtime_config = RuntimeConfig()
        self.runtime_config.factory_mode = TomlConfig(defines.factoryConfigPath).load().get("factoryMode", False)
        if self.runtime_config.factory_mode:
            set_log_level(logging.DEBUG)
        self.runtime_config.show_admin = self.runtime_config.factory_mode
        try:
            self.hwConfig.read_file()
        except ConfigException:
            self.logger.warning("Failed to read configuration file", exc_info=True)

        self.logger.info(str(self.hwConfig))

        self.logger.info("Initializing libHardware")

        self.hw = Hardware(self.hwConfig)

        # needed before init of other components (display etc)
        # TODO: Enable this once kit A64 do not require being turned on during manufacturing.
        #   Currently calibration needs to be performed in the factory.
        # if self.factoryMode and self.hw.isKit:
        #     self.factoryMode = False
        #     self.logger.warning("Factory mode disabled for kit")
        #

        self.logger.info("Initializing libNetwork")
        self.inet = Network(self.hw.cpuSerialNo)

        self.logger.info("Initializing display devices")
        if debug_display:
            devices = [debug_display]
        else:
            devices = [QtDisplay()]

        self.logger.info("Initializing libScreen")
        self.screen = Screen()

        self.logger.info("Registering config D-Bus services")
        self.system_bus = SystemBus()
        self.config0_dbus = self.system_bus.publish(Config0.__INTERFACE__, Config0(self.hwConfig, self.hw))

        self.logger.info("Initializing libDisplay")
        self.display = Display(
            self.hwConfig, devices, self.hw, self.inet, self.screen, self.runtime_config, self.action_manager,
        )

        self.logger.info("SL1 firmware initialized in %.03f", monotonic() - init_time)

    @property
    def state(self) -> PrinterState:
        return self._state

    @state.setter
    def state(self, value: PrinterState):
        if self._state != value:
            self.logger.info("Printer state changed: %s -> %s", self._state, value)
            self._state = value
            self.state_changed.emit(value)

    def exit(self):
        self.state = PrinterState.EXIT
        self.display.exit()
        self.exited.wait(timeout=60)
        self.screen.exit()
        self.hw.exit()
        self.action_manager.exit()
        self.config0_dbus.unpublish()

    def printer_run(self):
        self.hw.uvLed(False)
        self.hw.powerLed("normal")

        if self.hw.checkFailedBoot():
            self.display.pages["error"].setParams(
                text=_(
                    "The printer has booted from an alternative slot due to failed boot attempts using the primary "
                    "slot.\n\n Update the printer with up-to-date firmware ASAP to recover the primary slot.\n\n"
                    "This usually happens after a failed update, or due to a hardware failure. Printer settings may "
                    "have been reset. "
                )
            )
            self.display.doMenu("error")

        if self.firstRun:
            try:
                locale = pydbus.SystemBus().get("org.freedesktop.locale1")
                if locale.Locale == ["LANG=C"]:
                    self.hw.beepRepeat(1)
                    self.display.doMenu("setlanguage")

            except GLib.GError:
                self.logger.exception("Failed to obtain current locale.")

            if not self.hwConfig.is_factory_read() and not self.hw.isKit:
                self.display.pages["error"].setParams(text=_("Failed to load fans and LEDs factory calibration."))
                self.display.doMenu("error")

            if self.runtime_config.factory_mode and not list(Path(defines.internalProjectPath).rglob("*.sl1")):
                self.display.pages["error"].setParams(
                    text=_("Examples (any projects) are missing in the user storage.")
                )
                self.display.doMenu("error")

            if not self.runtime_config.factory_mode and self.hwConfig.showUnboxing:
                self.action_manager.start_unboxing(self.hw, self.hwConfig)
                self.display.doMenu("unboxing")
                self.action_manager.cleanup_unboxing()
                self.enter_menu(True)
            else:
                self.enter_menu(True)

        else:
            self.enter_menu(False)

    def enter_menu(self, first_run: bool) -> None:
        if first_run:
            if self.hwConfig.showWizard:
                self.hw.beepRepeat(1)
                self.display.doMenu("wizardinit")

            if self.display.hwConfig.uvPwm < self.hw.getMinPwm():
                self.hw.beepRepeat(1)
                self.display.doMenu("uvcalibrationstart")

            if not self.hwConfig.calibrated:
                self.hw.beepRepeat(1)
                self.display.doMenu("calibrationstart")

        last_exposure = Exposure.load(self.logger)
        if last_exposure:
            self.runtime_config.last_exposure = last_exposure
            Exposure.cleanup_last_data(self.logger)

            self.display.doMenu("finished")
        else:
            self.display.doMenu("home")

        self.firstRun = False

    def run(self):
        self.logger.info("SL1 firmware starting, PID: %d", os.getpid())
        self.logger.info("System version: %s", distro.version())
        self.start_time = monotonic()
        self.logger.info("Starting libHardware")
        self.hw.start()
        self.logger.info("Starting libDisplay")
        self.display.start()

        # Since display is initialized we can catch exceptions and report problems to display
        try:
            self.logger.info("Registering event handlers")
            self.inet.register_events()
            self.system_bus.get("org.freedesktop.locale1").PropertiesChanged.connect(self._locale_changed)
            self.system_bus.get("de.pengutronix.rauc", "/").PropertiesChanged.connect(self._rauc_changed)

            self.logger.info("Connecting motion controller")
            state = self.hw.connectMC()
            if state != MotConComState.OK:
                self.logger.info("Failed first motion controller connect attempt, state: %s", state)
                wait_page = PageWait(self.display)
                wait_page.fill(line1=_("Updating motion controller firmware"))
                wait_page.show()
                state = self.hw.connectMC(force_flash=True)

            if state != MotConComState.OK:
                raise Exception(f"Failed motion controller update attempt, state: {state}")

            PageStart(self.display).show()
            self.logger.info("Starting libScreen")
            self.screen.start()
            if not self.runtime_config.factory_mode:
                self.logger.info("Starting admin checker")
                self.admin_check = AdminCheck(self.runtime_config, self.hw, self.inet)

            self.logger.info("Loading slicer profiles")
            self.slicer_profile = SlicerProfile(defines.slicerProfilesFile)
            if not self.slicer_profile.load():
                self.logger.debug("Trying bundled slicer profiles")
                self.slicer_profile = SlicerProfile(defines.slicerProfilesFallback)
                if not self.slicer_profile.load():
                    self.logger.error("No suitable slicer profiles found")

            if self.slicer_profile.vendor:
                self.logger.info("Starting slicer profiles updater")
                self.slicer_profile_updater = SlicerProfileUpdater(self.inet, self.slicer_profile)

            # Force update network state (in case we missed network going online)
            # All network state handler should be already registered
            self.inet.force_refresh_state()

            self.logger.info("SL1 firmware started in %.03f seconds", monotonic() - self.start_time)
        except Exception as exception:
            self.exception = exception
            self.state = PrinterState.EXCEPTION
            if test_runtime.hard_exceptions:
                raise exception
            self.logger.exception("Printer run() init failed")
            code = getattr(exception, "CODE") if hasattr(exception, "CODE") else Sl1Codes.UNKNOWN.code
            self.display.pages["exception"].setParams(
                text=_("Error code: %s\n\n") % code
                + _(
                    "An unexpected error has occurred :-(.\n\n"
                    "You can turn the printer off by pressing the front power button.\n\n"
                    "Please follow the instructions in Chapter 3.1 in the handbook to learn how to save a log file. "
                    "Please send the log to us and help us improve the printer.\n\n"
                    "Thank you!"
                )
            )
            self.display.doMenu("exception")

        try:
            self.exited.clear()
            self.state = PrinterState.RUNNING
            while self.state != PrinterState.EXIT:
                self.printer_run()

        except Exception as exception:
            self.exception = exception
            self.state = PrinterState.EXCEPTION
            if test_runtime.hard_exceptions:
                raise exception
            self.logger.exception("run() exception:")
            code = getattr(exception, "CODE") if hasattr(exception, "CODE") else Sl1Codes.UNKNOWN.code
            self.display.pages["exception"].setParams(
                text=_("Error code: %s\n\n") % code
                + _(
                    "An unexpected error has occurred :-(.\n\n"
                    "The SL1 will finish the print if you are currently printing.\n\n"
                    "You can turn the printer off by pressing the front power button.\n\n"
                    "Please follow the instructions in Chapter 3.1 in the handbook to learn how to save a log file. "
                    "Please send the log to us and help us improve the printer.\n\n"
                    "Thank you!"
                )
            )
            self.display.doMenu("exception")

        if self.action_manager.exposure and self.action_manager.exposure.in_progress:
            self.action_manager.exposure.waitDone()

        self.exited.set()

    def _locale_changed(self, __, changed, ___):
        if "Locale" not in changed:
            return

        lang = re.sub(r"LANG=(.*)\..*", r"\g<1>", changed["Locale"][0])

        try:
            self.logger.debug("Obtaining translation: %s", lang)
            translation = gettext.translation("sl1fw", localedir=defines.localedir, languages=[lang], fallback=True)
            self.logger.info("Installing translation: %s", lang)
            translation.install(names="ngettext")
        except (IOError, OSError):
            self.logger.exception("Translation for %s cannot be installed.", lang)

    def _rauc_changed(self, __, changed, ___):
        if "Operation" in changed:
            if changed["Operation"] == "idle":
                if self.state == PrinterState.UPDATING:
                    self.state = PrinterState.RUNNING

            else:
                self.state = PrinterState.UPDATING

    def get_actual_page(self):
        return self.display.actualPage

    def _exposure_changed(self):
        if self.state == PrinterState.PRINTING:
            if not self.action_manager.exposure or self.action_manager.exposure.done:
                self.state = PrinterState.RUNNING

        else:
            if self.action_manager.exposure and not self.action_manager.exposure.done:
                self.state = PrinterState.PRINTING

    def _unboxing_changed(self):
        unboxing = self.action_manager.unboxing
        if self.state == PrinterState.UNBOXING:
            if not unboxing or unboxing.state in [
                UnboxingState.FINISHED,
                UnboxingState.CANCELED,
            ]:
                self.state = PrinterState.RUNNING

        else:
            if unboxing and unboxing.state not in [
                UnboxingState.FINISHED,
                UnboxingState.CANCELED,
            ]:
                self.state = PrinterState.UNBOXING

    def _display_test_changed(self):
        display_test = self.action_manager.display_test
        if self.state == PrinterState.DISPLAY_TEST:
            if not display_test or display_test.state != DisplayTest0State.FINISHED:
                self.state = PrinterState.RUNNING

        else:
            if display_test and display_test.state != DisplayTest0State.FINISHED:
                self.state = PrinterState.DISPLAY_TEST
