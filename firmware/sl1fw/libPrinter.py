# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import os
import logging
from time import time, sleep
from pydbus import SystemBus
from gi.repository import GLib
import threading
import gettext
import re
from dbus.mainloop.glib import DBusGMainLoop

from sl1fw import defines
from sl1fw import libConfig
from sl1fw.api.printer0 import Printer0


class Printer(object):

    def __init__(self, debugDisplay=None):
        startTime = time()
        self.running = True
        self.exited = threading.Event()
        # TODO: Event should be set by default to enable test tear down

        self.logger = logging.getLogger(__name__)
        self.logger.info("SL1 firmware started")

        factory_defaults = libConfig.TomlConfig(defines.hwConfigFactoryDefaultsFile).load()
        self.hwConfig = libConfig.HwConfig(defines.hwConfigFile, defaults = factory_defaults)
        self.hwConfig.logAllItems()
        self.config = libConfig.PrintConfig(self.hwConfig)

        # TODO: This executes a new thread in case of tests, and we are in __init__
        from sl1fw.libHardware import Hardware
        self.hw = Hardware(self.hwConfig, self.config)

        # needed before init of other components (display etc)
        # TODO: Enable this once kit A64 do not require being turned during manufacturing.
        #   Currently calibration needs to be performed in the factory.
        # if self.hwConfig.factoryMode and self.hw.isKit:
        #     self.hwConfig.factoryMode = False
        #     self.logger.warning("Factory mode disabled for kit")
        # #endif

        from sl1fw.libNetwork import Network
        self.inet = Network()

        if debugDisplay:
            devices = [debugDisplay]
        else:
            # TODO: This executes a new thread and we are in __init__
            from sl1fw.libQtDisplay import QtDisplay
            qtdisplay = QtDisplay()

            # TODO: This executes a new thread and we are in __init__
            from sl1fw.libWebDisplay import WebDisplay
            webdisplay = WebDisplay()

            devices = [qtdisplay, webdisplay]
        #endif

        # TODO: This executes a new thread and we are in __init__
        from sl1fw.libScreen import Screen
        self.screen = Screen(self.hwConfig)

        self.logger.debug("Registering printer dbus services")
        self.printer0 = Printer0(self)
        SystemBus().publish(self.printer0.INTERFACE, self.printer0)

        from sl1fw.libPages import PageWait
        from sl1fw.pages.start import PageStart
        from sl1fw.libDisplay import Display
        self.display = Display(self.hwConfig, self.config, devices, self.hw, self.inet, self.screen, self.printer0)

        self.hw.connectMC(PageWait(self.display), PageStart(self.display))

        # Start DBus event loop in separate thread
        self.logger.debug("Starting dbus event loop")
        DBusGMainLoop(set_as_default=True)
        self.eventLoop = GLib.MainLoop()
        self.eventThread = threading.Thread(target=self.loopThread)
        # TODO: This executes a new thread and we are in __init__
        self.eventThread.start()

        self.inet.start_net_monitor()

        self.logger.info("Start time: %f secs", time() - startTime)
    #endclass


    def __del__(self):
        self.exit()
    #enddef


    def exit(self):
        self.running = False
        self.display.exit()
        self.exited.wait()
        self.screen.exit()
        self.hw.exit()
        self.eventLoop.quit()
        self.eventThread.join()
    #enddef


    def start(self):
        from sl1fw.libExposure import Exposure
        firstRun = True
        self.exited.clear()

        try:
            while self.running:
                self.hw.uvLed(False)
                self.hw.powerLed("normal")

                self.expo = Exposure(self.hwConfig, self.config, self.display, self.hw, self.screen)
                self.display.initExpo(self.expo)
                self.screen.cleanup()

                if self.hw.checkFailedBoot():
                    self.display.pages['error'].setParams(
                        text=_("The printer has booted from an alternative slot due to failed boot attempts using the primary slot.\n\n"
                            "Update the printer with up-to-date firmware ASAP to recover the primary slot.\n\n"
                            "This usually happens after a failed update, or due to a hardware failure. Printer settings may have been reset."))
                    self.display.doMenu("error")
                #endif

                if firstRun:
                    if not self.hwConfig.defaultsSet() and not self.hw.isKit:
                        self.display.pages['error'].setParams(
                            text=_("Failed to load fans and LEDs factory calibration."))
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
                        sleep(0.5)
                    elif self.hwConfig.showWizard:
                        self.hw.beepRepeat(1)
                        self.display.doMenu("wizardinit")
                        sleep(0.5)
                    elif not self.display.hwConfig.calibrated:
                        self.display.pages['yesno'].setParams(
                                pageTitle = N_("Calibrate now?"),
                                text = _("Printer is not calibrated!\n\n"
                                    "Calibrate now?"))
                        self.hw.beepRepeat(1)
                        if self.display.doMenu("yesno"):
                            self.display.doMenu("calibration1")
                        #endif
                    #endif
                #endif

                lastProject = libConfig.TomlConfig(defines.lastProjectData).load()
                if lastProject:
                    self.display.pages['finished'].data = lastProject
                    try:
                        os.remove(defines.lastProjectData)
                    except Exception as e:
                        self.logger.exception("LastProject cleanup exception:")
                    #endtry
                    self.display.doMenu("finished")
                else:
                    self.display.doMenu("home")
                #endif
                firstRun = False
            #endwhile

        except Exception:
            self.logger.exception("run() exception:")
            self.hw.powerLed("error")
            self.display.pages['exception'].setParams(text =
                    "An unexpected error has occured :-(.\n\n"
                    "The SL1 will finish the print if you are currently printing.\n\n"
                    "You can turn the printer off by pressing the front power button.\n\n"
                    "Please follow the instructions in Chapter 3.1 in the handbook to learn how to save a log file. Please send the log to us and help us improve the printer.\n\n"
                    "Thank you!")
            self.display.forcePage("exception")
            if hasattr(self, 'expo') and self.expo.inProgress():
                self.expo.waitDone()
            #endif
            self.hw.uvLed(False)
            self.hw.stopFans()
            self.hw.motorsRelease()
            while not self.display.hw.getPowerswitchState():
                sleep(0.5)
            #endwhile
            self.display.shutDown(True)
        #endtry

        if hasattr(self, 'expo') and self.expo.inProgress():
            self.expo.waitDone()
        #endif

        self.exited.set()
    #enddef

    def loopThread(self) -> None:
        self.logger.debug("Registering dbus event handlers")
        locale = SystemBus().get("org.freedesktop.locale1")
        locale.PropertiesChanged.connect(self.localeChanged)
        wificonfig = SystemBus().get("cz.prusa3d.sl1.wificonfig")
        wificonfig.PropertiesChanged.connect(self.wificonfigChanged)

        self.logger.debug("Starting printer event loop")
        self.eventLoop.run()
        self.logger.debug("Printer event loop exited")
    #enddef

    def localeChanged(self, service, changed, data):
        if not 'Locale' in changed:
            return
        #endif

        try:
            lang = re.sub(r"LANG=(.*)\..*", r"\g<1>", changed['Locale'][0])
        except:
            self.logger.exception("Failed to determine new locale language")
            return
        #endtry

        try:
            self.logger.debug("Obtaining translation: %s" % lang)
            translation = gettext.translation('sl1fw', localedir=defines.localedir, languages=[lang], fallback=True)
            self.logger.debug("Installing translation: %s" % lang)
            translation.install()
        except:
            self.logger.exception("Translation for %s cannot be installed.", lang)
        #endtry
    #enddef

    def wificonfigChanged(self, service, changed, data):
        if not 'APs' in changed:
            return
        #endif

        if self.display.actualPage == self.display.pages['network']:
            self.display.pages['network'].apsChanged()
        #endif
    #enddef

    def get_actual_page(self):
        return self.display.actualPage
    #enddef

    def get_actual_page_stack(self):
        return self.display.actualPageStack
    #enddef

#endclass
