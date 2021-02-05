# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# TODO: Fix following pylint problems
# pylint: disable=too-many-statements
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-branches

import gettext
import logging
import os
import re
import hashlib
import threading
import subprocess
import weakref
from pathlib import Path
from time import monotonic
from typing import Optional

import distro
import pydbus
from PySignal import Signal
from gi.repository import GLib
from pydbus import SystemBus

from prusaerrors.sl1.codes import Sl1Codes

from sl1fw import defines
from sl1fw.api.config0 import Config0
from sl1fw.api.logs0 import Logs0
from sl1fw.errors.exceptions import ConfigException
from sl1fw.functions.wizards import kit_unboxing_wizard, unboxing_wizard
from sl1fw.functions.files import save_all_remain_wizard_history
from sl1fw.functions.miscellaneous import toBase32hex
from sl1fw.libAsync import AdminCheck
from sl1fw.libAsync import SlicerProfileUpdater
from sl1fw.configs.hw import HwConfig
from sl1fw.configs.toml import TomlConfig
from sl1fw.configs.runtime import RuntimeConfig
from sl1fw.configs.stats import TomlConfigStats
from sl1fw.libDisplay import Display
from sl1fw.libHardware import Hardware
from sl1fw.libHardware import MotConComState
from sl1fw.libNetwork import Network
from sl1fw.libQtDisplay import QtDisplay
from sl1fw.screen.screen import Screen
from sl1fw.screen.printer_model import PrinterModel
from sl1fw.pages.wait import PageWait
from sl1fw.state_actions.manager import ActionManager
from sl1fw.slicer.slicer_profile import SlicerProfile
from sl1fw.states.printer import PrinterState
from sl1fw.states.wizard import WizardState
from sl1fw import test_runtime


class Printer:
    def __init__(self, debug_display=None):
        self.logger = logging.getLogger(__name__)
        self._printer_identifier = None
        init_time = monotonic()
        self._exception: Optional[Exception] = None
        self.exception_changed = Signal()
        self.start_time = None
        self.admin_check = None
        self.slicer_profile = None
        self.slicer_profile_updater = None
        self._state = PrinterState.INIT
        self.state_changed = Signal()
        self.firstRun = True
        self.action_manager = ActionManager()
        self.action_manager.exposure_change.connect(self._exposure_changed)
        self.action_manager.wizard_changed.connect(self._wizard_changed)
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
        self.runtime_config.factory_mode = defines.factory_enable.exists() or \
            TomlConfig(defines.factoryConfigPath).load().get("factoryMode", False)  # Single value TOML now deprecated
        self.logger.info("Factory mode: %s", self.runtime_config.factory_mode)
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

        self.logger.info("Initializing Screen")
        self.screen = Screen(self.hwConfig)

        self.logger.info("Registering config D-Bus services")
        self.system_bus = SystemBus()
        self.config0_dbus = self.system_bus.publish(Config0.__INTERFACE__, Config0(self.hwConfig, self.hw))

        self.logger.info("registering log0 dbus interface")
        self.logs0_dbus = self.system_bus.publish(Logs0.__INTERFACE__, Logs0(self.hw))

        self.logger.info("Initializing libDisplay")
        self.display = Display(
            self.hwConfig, devices, self.hw, self.inet, self.screen, self.runtime_config, self.action_manager,
        )
        try:
            TomlConfigStats(defines.statsData, self.hw).update_reboot_counter()
        except Exception:
            self.logger.error("Error when update 'system_up_since' statistics.")

        self.logger.info("SL1 firmware initialized in %.03f", monotonic() - init_time)

    @property
    def state(self) -> PrinterState:
        return self._state

    @state.setter
    def state(self, value: PrinterState):
        if self._state != value:
            self.logger.info("Printer state changed: %s -> %s", self._state, value)
            self._state = value
            self.state_changed.emit()

    @property
    def exception(self) -> Exception:
        return self._exception

    @exception.setter
    def exception(self, value: Exception):
        self._exception = value
        self.exception_changed.emit()

    def exit(self):
        self.state = PrinterState.EXIT
        self.display.exit()
        self.screen.exit()
        self.exited.wait(timeout=60)
        self.hw.exit()
        self.action_manager.exit()
        self.config0_dbus.unpublish()
        self.logs0_dbus.unpublish()

    def printer_run(self):
        self.hw.uvLed(False)
        self.hw.powerLed("normal")

        if self.hw.checkFailedBoot():
            self.display.pages["error"].setParams(code=Sl1Codes.ALTERNATIVE_SLOT_BOOT.raw_code)
            self.display.doMenu("error")

        if self.screen.printer_model == PrinterModel.NONE:
            self.display.pages["error"].setParams(code=Sl1Codes.DISPLAY_TEST_FAILED.raw_code)
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
                self.display.pages["error"].setParams(code=Sl1Codes.FAILED_TO_LOAD_FACTORY_LEDS_CALIBRATION.raw_code)
                self.display.doMenu("error")

            if self.runtime_config.factory_mode and not list(Path(defines.internalProjectPath).rglob("*%s" % list(self.screen.printer_model.extensions)[0])):
                self.display.pages["error"].setParams(code=Sl1Codes.MISSING_EXAMPLES.raw_code)
                self.display.doMenu("error")

            if not self.runtime_config.factory_mode and self.hwConfig.showUnboxing:
                if self.hw.isKit:
                    unboxing = kit_unboxing_wizard(self.action_manager, self.hw, self.hwConfig, self.runtime_config)
                else:
                    unboxing = unboxing_wizard(self.action_manager, self.hw, self.hwConfig, self.runtime_config)
                self.logger.info("Running unboxing wizard")
                unboxing.join()
                self.logger.info("Unboxing finished")

            if self.hwConfig.showWizard:
                self.hw.beepRepeat(1)
                self.display.doMenu("wizardinit")

            if self.display.hwConfig.uvPwm < self.screen.printer_model.calibration(self.hw.is500khz).min_pwm:
                self.hw.beepRepeat(1)
                self.display.doMenu("uvcalibrationstart")

            if not self.hwConfig.calibrated:
                self.hw.beepRepeat(1)
                self.display.doMenu("calibrationstart")

            save_all_remain_wizard_history()

        self.action_manager.load_exposure(self.hw)
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
            self.system_bus.get("org.freedesktop.locale1").PropertiesChanged.connect(weakref.proxy(self._locale_changed))
            self.system_bus.get("de.pengutronix.rauc", "/").PropertiesChanged.connect(weakref.proxy(self._rauc_changed))

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
                self.slicer_profile_updater = SlicerProfileUpdater(self.inet, self.slicer_profile, self.screen.printer_model.name)

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

    def _wizard_changed(self):
        self.logger.debug("Wizard changed")
        wizard = self.action_manager.wizard
        if self.state == PrinterState.WIZARD:
            if not wizard or wizard.state in WizardState.finished_states():
                self.state = PrinterState.RUNNING
        else:
            if wizard and wizard.state not in WizardState.finished_states():
                self.state = PrinterState.WIZARD

    @property
    def id(self) -> str:
        """Return a hex string identification for the printer image."""

        if self._printer_identifier is None:
            boot = 1
            output = subprocess.check_output("lsblk -l | grep -e '/$' | awk '{print $1}'", shell=True)
            slot = output.decode().strip()
            if slot not in ["mmcblk2p2", "mmcblk2p3"]:
                boot = 0

            mac_eth0 = self.inet.get_eth_mac()
            cpu_serial = self.hw.cpuSerialNo.strip(" *")
            emmc_serial = self.hw.emmc_serial
            trusted_image = 0

            hash_hex = hashlib.sha256((emmc_serial+mac_eth0+cpu_serial).encode()).hexdigest()
            binary = str(trusted_image)+str(boot)+bin(int(hash_hex[:10], 16))[2:-2]
            self._printer_identifier = toBase32hex(int(binary, 2))

        return self._printer_identifier
