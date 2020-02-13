# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import gettext
import logging
import os
import re
import threading
from pathlib import Path
from time import sleep, monotonic
from typing import Optional

import distro
from PySignal import Signal
from pydbus import SystemBus

from sl1fw import defines
from sl1fw import libConfig
from sl1fw.api.config0 import Config0
from sl1fw.libAsync import AdminCheck
from sl1fw.libAsync import SlicerProfileUpdater
from sl1fw.libConfig import HwConfig, ConfigException, TomlConfig, RuntimeConfig
from sl1fw.libDisplay import Display
from sl1fw.libHardware import Hardware
from sl1fw.libHardware import MotConComState
from sl1fw.libNetwork import Network
from sl1fw.libQtDisplay import QtDisplay
from sl1fw.libScreen import Screen
from sl1fw.libWebDisplay import WebDisplay
from sl1fw.pages.start import PageStart
from sl1fw.pages.wait import PageWait
from sl1fw.printer_state import PrinterState
from sl1fw.project.manager import ExposureManager
from sl1fw.slicer.slicer_profile import SlicerProfile


class Printer:

    def __init__(self, debugDisplay=None):
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
        self.exposure_manager = ExposureManager()
        self.exposure_manager.exposure_change.connect(self._exposure_changed)
        self.exited = threading.Event()
        self.exited.set()
        self.logger.info("SL1 firmware initializing")

        self.logger.debug("Initializing hwconfig")
        self.hwConfig = HwConfig(file_path=Path(defines.hwConfigFile),
                                 factory_file_path=Path(defines.hwConfigFactoryDefaultsFile),
                                 is_master=True)
        self.runtime_config = RuntimeConfig()
        self.runtime_config.factory_mode = TomlConfig(defines.factoryConfigFile).load().get('factoryMode', False)
        self.runtime_config.show_admin = self.runtime_config.factory_mode
        try:
            self.hwConfig.read_file()
        except ConfigException:
            self.logger.warning("Failed to read configuration file", exc_info=True)
        #endtry
        self.logger.info(str(self.hwConfig))

        self.logger.debug("Initializing libHardware")

        self.hw = Hardware(self.hwConfig)

        # needed before init of other components (display etc)
        # TODO: Enable this once kit A64 do not require being turned on during manufacturing.
        #   Currently calibration needs to be performed in the factory.
        # if self.factoryMode and self.hw.isKit:
        #     self.factoryMode = False
        #     self.logger.warning("Factory mode disabled for kit")
        # #endif

        self.logger.debug("Initializing libNetwork")
        self.inet = Network(self.hw.cpuSerialNo)

        self.logger.debug("Initializing display devices")
        if debugDisplay:
            devices = [debugDisplay]
        else:
            devices = [QtDisplay(), WebDisplay()]
        #endif

        self.logger.debug("Initializing libScreen")
        self.screen = Screen()

        self.logger.debug("Registering config D-Bus services")
        self.system_bus = SystemBus()
        self.config0_dbus = self.system_bus.publish(Config0.__INTERFACE__, Config0(self.hwConfig))

        self.logger.debug("Initializing libDisplay")
        self.display = Display(self.hwConfig, devices, self.hw, self.inet, self.screen, self.runtime_config,
                               self.exposure_manager)

        self.logger.debug("SL1 firmware initialized in %.03f", monotonic() - init_time)
    #endclass

    @property
    def state(self) -> PrinterState:
        return self._state
    #enddef

    @state.setter
    def state(self, value: PrinterState):
        if self._state != value:
            self._state = value
            self.state_changed.emit(value)
        #endif
    #enddef

    def exit(self):
        self.state = PrinterState.EXIT
        self.display.exit()
        self.exited.wait(timeout=60)
        self.screen.exit()
        self.hw.exit()
        self.exposure_manager.exit()
        self.config0_dbus.unpublish()
    #enddef

    def printer_run(self):
        self.hw.uvLed(False)
        self.hw.powerLed("normal")

        if self.hw.checkFailedBoot():
            self.display.pages['error'].setParams(
                text=_("The printer has booted from an alternative slot due to failed boot attempts using the primary slot.\n\n"
                       "Update the printer with up-to-date firmware ASAP to recover the primary slot.\n\n"
                       "This usually happens after a failed update, or due to a hardware failure. Printer settings may have been reset."))
            self.display.doMenu("error")
        #endif

        if self.firstRun:
            if self.hwConfig.showI18nSelect:
                self.hw.beepRepeat(1)
                self.display.doMenu("setlanguage")
            #endif

            if not self.hwConfig.is_factory_read() and not self.hw.isKit:
                self.display.pages['error'].setParams(
                    text=_("Failed to load fans and LEDs factory calibration."))
                self.display.doMenu("error")
            #endif

            if self.runtime_config.factory_mode and not list(Path(defines.internalProjectPath).rglob("*.sl1")):
                self.display.pages['error'].setParams(
                    text=_("Examples (any projects) are missing in the user storage."))
                self.display.doMenu("error")
            #endif

            if self.hwConfig.showUnboxing:
                self.hw.beepRepeat(1)
                if self.hw.isKit:
                    # force page title
                    self.display.pages['unboxing4'].pageTitle = N_("Unboxing step 1/1")
                    self.display.doMenu("unboxing4")
                else:
                    self.display.doMenu("unboxing1")
                #endif
                # continue to wizard directly
                self.display.doMenu("wizardinit")
                sleep(0.5)
            elif self.hwConfig.showWizard:
                self.hw.beepRepeat(1)
                self.display.doMenu("wizardinit")
                sleep(0.5)
            elif not self.hwConfig.calibrated:
                self.display.pages['yesno'].setParams(
                        pageTitle = N_("Calibrate now?"),
                        text = _("Printer is not calibrated!\n\n"
                                 "Calibrate now?"))
                self.hw.beepRepeat(1)
                if self.display.doMenu("yesno"):
                    self.display.doMenu("calibrationstart")
                #endif
            #endif
        #endif

        lastProject = libConfig.TomlConfig(defines.lastProjectData).load()
        if lastProject:
            self.runtime_config.last_project_data = lastProject
            try:
                os.remove(defines.lastProjectData)
            except FileNotFoundError:
                self.logger.exception("LastProject cleanup exception:")
            #endtry
            self.display.doMenu("finished")
        else:
            self.display.doMenu("home")
        #endif
        self.firstRun = False
    #enddef

    def run(self):
        self.logger.info("SL1 firmware starting, PID: %d", os.getpid())
        self.logger.info("System version: %s", distro.version())
        self.start_time = monotonic()
        self.logger.debug("Starting libHardware")
        self.hw.start()
        self.logger.debug("Starting libDisplay")
        self.display.start()

        # Since display is initialized we can catch exceptions and report problems to display
        try:
            self.logger.debug("Registering event handlers")
            self.inet.register_events()
            self.system_bus.get("org.freedesktop.locale1").PropertiesChanged.connect(self._locale_changed)
            self.system_bus.get("de.pengutronix.rauc", "/").PropertiesChanged.connect(self._rauc_changed)

            self.logger.debug("Connecting motion controller")
            state = self.hw.connectMC()
            if state != MotConComState.OK:
                self.logger.info("Failed first motion controller connect attempt, state: %s", state)
                waitPage = PageWait(self.display)
                waitPage.fill(line1=_("Updating motion controller firmware"))
                waitPage.show()
                state = self.hw.connectMC(force_flash=True)
            #endif
            if state != MotConComState.OK:
                raise Exception(f"Failed motion controller update attempt, state: {state}")
            #endif
            PageStart(self.display).show()
            self.logger.debug("Starting libScreen")
            self.screen.start()
            if not self.runtime_config.factory_mode:
                self.logger.debug("Starting admin checker")
                self.admin_check = AdminCheck(self.runtime_config, self.hw, self.inet)
            #endif
            self.logger.debug("Loading slicer profiles")
            self.slicer_profile = SlicerProfile(defines.slicerProfilesFile)
            if not self.slicer_profile.load():
                self.logger.debug("Trying bundled slicer profiles")
                self.slicer_profile = SlicerProfile(defines.slicerProfilesFallback)
                if not self.slicer_profile.load():
                    self.logger.error("No suitable slicer profiles found")
                #endif
            #endif
            if self.slicer_profile.vendor:
                self.logger.debug("Starting slicer profiles updater")
                self.slicer_profile_updater = SlicerProfileUpdater(self.inet, self.slicer_profile)
            #endif

            # Force update network state (in case we missed network going online)
            # All network state handler should be already registered
            self.inet.force_refresh_state()

            self.logger.debug("SL1 firmware started in %.03f seconds", monotonic() - self.start_time)
        except Exception as exception:
            self.exception = exception
            self.state = PrinterState.EXCEPTION
            if defines.testing:
                raise exception
            self.logger.exception("Printer run() init failed")
            self.display.pages['exception'].setParams(
                text=_("An unexpected error has occured :-(.\n\n"
                     "You can turn the printer off by pressing the front power button.\n\n"
                     "Please follow the instructions in Chapter 3.1 in the handbook to learn how to save a log file. "
                     "Please send the log to us and help us improve the printer.\n\n"
                     "Thank you!"))
            self.display.doMenu("exception")

        try:
            self.exited.clear()
            self.state = PrinterState.RUNNING
            while self.state != PrinterState.EXIT:
                self.printer_run()
            #endwhile
        except Exception as exception:
            self.exception = exception
            self.state = PrinterState.EXCEPTION
            if defines.testing:
                raise exception
            self.logger.exception("run() exception:")
            self.display.pages['exception'].setParams(
                text=_("An unexpected error has occured :-(.\n\n"
                      "The SL1 will finish the print if you are currently printing.\n\n"
                      "You can turn the printer off by pressing the front power button.\n\n"
                      "Please follow the instructions in Chapter 3.1 in the handbook to learn how to save a log file. "
                      "Please send the log to us and help us improve the printer.\n\n"
                      "Thank you!"))
            self.display.doMenu("exception")
        #endtry

        if self.exposure_manager.exposure and self.exposure_manager.exposure.in_progress:
            self.exposure_manager.exposure.waitDone()
        #endif

        self.exited.set()
    #enddef

    def _locale_changed(self, __, changed, ___):
        if 'Locale' not in changed:
            return
        #endif

        lang = re.sub(r"LANG=(.*)\..*", r"\g<1>", changed['Locale'][0])

        try:
            self.logger.debug("Obtaining translation: %s", lang)
            translation = gettext.translation('sl1fw', localedir=defines.localedir, languages=[lang], fallback=True)
            self.logger.debug("Installing translation: %s", lang)
            translation.install(names="ngettext")
        except (IOError, OSError):
            self.logger.exception("Translation for %s cannot be installed.", lang)
        #endtry
    #enddef

    def _rauc_changed(self, __, changed, ___):
        if "Operation" in changed:
            if changed["Operation"] == "idle":
                if self.state == PrinterState.UPDATING:
                    self.state = PrinterState.RUNNING
                #endif
            else:
                self.state = PrinterState.UPDATING
            #endif
        #endif
    #enddef

    def get_actual_page(self):
        return self.display.actualPage
    #enddef

    def _exposure_changed(self):
        if self.state == PrinterState.PRINTING:
            if not self.exposure_manager.exposure or self.exposure_manager.exposure.done:
                self.state = PrinterState.RUNNING
            #endif
        else:
            if self.exposure_manager.exposure and not self.exposure_manager.exposure.done:
                self.state = PrinterState.PRINTING
            #endif
        #endif
    #enddef

#endclass
