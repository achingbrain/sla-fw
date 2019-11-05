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
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from pydbus import SystemBus

from sl1fw import defines
from sl1fw import libConfig
from sl1fw.api.config0 import Config0
from sl1fw.api.exposure0 import Exposure0
from sl1fw.api.printer0 import Printer0
from sl1fw.libAsync import AdminCheck, SlicerProfileUpdater
from sl1fw.libConfig import HwConfig, ConfigException, TomlConfig
from sl1fw.libExposure import Exposure
from sl1fw.libHardware import MotConComState
from sl1fw.pages.start import PageStart
from sl1fw.pages.wait import PageWait
from sl1fw.slicer.profile_parser import ProfileParser


class Printer:

    def __init__(self, debugDisplay=None):
        self.logger = logging.getLogger(__name__)
        init_time = monotonic()
        self.start_time = None
        self.admin_check = None
        self.slicer_profile = None
        self.slicer_profile_updater = None
        self.running = True
        self.firstRun = True
        self.expo: Optional[Exposure] = None
        self.exposure_dbus_objects = set()
        self.exited = threading.Event()
        self.exited.set()
        self.logger.info("SL1 firmware initializing")

        self.logger.debug("Initializing hwconfig")
        self.hwConfig = HwConfig(file_path=Path(defines.hwConfigFile),
                                 factory_file_path=Path(defines.hwConfigFactoryDefaultsFile),
                                 is_master=True)
        self.factoryMode = TomlConfig(defines.factoryConfigFile).load().get('factoryMode', False)
        try:
            self.hwConfig.read_file()
        except ConfigException:
            self.logger.warning("Failed to read configuration file", exc_info=True)
        #endtry
        self.logger.info(str(self.hwConfig))

        self.logger.debug("Initializing libHardware")
        from sl1fw.libHardware import Hardware
        self.hw = Hardware(self.hwConfig)

        # needed before init of other components (display etc)
        # TODO: Enable this once kit A64 do not require being turned on during manufacturing.
        #   Currently calibration needs to be performed in the factory.
        # if self.factoryMode and self.hw.isKit:
        #     self.factoryMode = False
        #     self.logger.warning("Factory mode disabled for kit")
        # #endif

        self.logger.debug("Initializing libNetwork")
        from sl1fw.libNetwork import Network
        self.inet = Network(self.hw.cpuSerialNo)

        self.logger.debug("Initializing display devices")
        if debugDisplay:
            devices = [debugDisplay]
        else:
            from sl1fw.libQtDisplay import QtDisplay
            from sl1fw.libWebDisplay import WebDisplay
            devices = [QtDisplay(), WebDisplay()]
        #endif

        self.logger.debug("Initializing libScreen")
        from sl1fw.libScreen import Screen
        self.screen = Screen()

        self.logger.debug("Registering printer D-Bus services")
        self.printer0 = Printer0(self)
        self.config0 = Config0(self.hwConfig)
        SystemBus().publish(self.printer0.__INTERFACE__, self.printer0)
        SystemBus().publish(self.config0.__INTERFACE__, self.config0)

        self.logger.debug("Initializing libDisplay")
        from sl1fw.libDisplay import Display
        self.display = Display(self.hwConfig, devices, self.hw, self.inet, self.screen, self.printer0)

        self.logger.debug("Initializing D-Bus event loop")
        DBusGMainLoop(set_as_default=True)
        self.eventLoop = GLib.MainLoop()
        self.eventThread = threading.Thread(target=self.loopThread)
        self.inet.register_events()

        self.logger.debug(f"SL1 firmware initialized in {monotonic() - init_time}")
    #endclass

    def exit(self):
        self.running = False
        self.display.exit()
        self.exited.wait(timeout=60)
        self.screen.exit()
        self.hw.exit()
        self.eventLoop.quit()
        for obj in self.exposure_dbus_objects:
            obj.unpublish()
        #endfor
        self.config0_dbus.unpublish()
        self.printer0_dbus.unpublish()
        if self.eventThread.is_alive():
            self.eventThread.join()
        #endif
    #enddef

    def printer_run(self):
        self.hw.uvLed(False)
        self.hw.powerLed("normal")

        self.expo = Exposure(self.hwConfig, self.hw, self.screen)
        self.logger.debug("Created new exposure object id: %s", self.expo.instance_id)
        self.exposure_dbus_objects.add(SystemBus().publish(
            Exposure0.__INTERFACE__,
            (Exposure0.dbus_path(self.expo.instance_id),
             Exposure0(self.expo))))
        self.display.initExpo(self.expo)
        self.screen.cleanup()

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

            if self.factoryMode and not list(Path(defines.internalProjectPath).rglob("*.sl1")):
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
            self.display.pages['finished'].data = lastProject
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
        self.logger.debug("Starting D-Bus event thread")
        self.eventThread.start()
        try:
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
            self.logger.debug("Starting admin checker")
            if not self.factoryMode:
                self.admin_check = AdminCheck(self.display, self.inet)
            #endif
            self.logger.debug("Loading slicer profiles")
            self.slicer_profile = ProfileParser().parse(defines.slicerProfilesFile)
            if not self.slicer_profile:
                self.logger.debug("Trying bundled slicer profiles")
                self.slicer_profile = ProfileParser().parse(defines.slicerProfilesFallback)
                if not self.slicer_profile:
                    self.logger.error("No suitable slicer profiles found")
                #endif
            #endif
            if self.slicer_profile:
                self.logger.debug("Starting slicer profiles updater")
                self.slicer_profile_updater = SlicerProfileUpdater(self.inet, self.slicer_profile)
            #endif
            self.logger.debug(f"SL1 firmware started in {monotonic() - self.start_time} seconds")
        except Exception as exception:
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
            while self.running:
                self.printer_run()
            #endwhile
        except Exception as exception:
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

        if self.expo and self.expo.inProgress():
            self.expo.waitDone()
        #endif

        self.exited.set()
    #enddef

    def loopThread(self) -> None:
        self.logger.debug("Registering dbus event handlers")
        locale = SystemBus().get("org.freedesktop.locale1")
        locale.PropertiesChanged.connect(self.localeChanged)

        self.logger.debug("Starting printer event loop")
        self.eventLoop.run()
        self.logger.debug("Printer event loop exited")
    #enddef

    def localeChanged(self, __, changed, ___):
        if 'Locale' not in changed:
            return
        #endif

        lang = re.sub(r"LANG=(.*)\..*", r"\g<1>", changed['Locale'][0])

        try:
            self.logger.debug("Obtaining translation: %s" % lang)
            translation = gettext.translation('sl1fw', localedir=defines.localedir, languages=[lang], fallback=True)
            self.logger.debug("Installing translation: %s" % lang)
            translation.install(names=("ngettext"))
        except (IOError, OSError):
            self.logger.exception("Translation for %s cannot be installed.", lang)
        #endtry
    #enddef

    def get_actual_page(self):
        return self.display.actualPage
    #enddef

    def get_actual_page_stack(self):
        return self.display.actualPageStack
    #enddef

#endclass
