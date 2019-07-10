# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import os
import logging
from time import time, sleep
import toml
from pydbus import SystemBus
from gi.repository import GLib
import threading
import gettext
import re

import sl1fw
from sl1fw import defines


class Printer(object):

    def __init__(self, debugDisplay=None):
        startTime = time()
        self.running = True

        self.logger = logging.getLogger(__name__)
        self.logger.info("SL1 firmware started - version %s", defines.swVersion)

        from sl1fw import libConfig
        try:
            with open(defines.hwConfigFactoryDefaultsFile, "r") as factory:
                factory_defaults = toml.load(factory)
            #endwith
        except:
            self.logger.exception("Failed to load factory defaults")
            factory_defaults = {}
        #endtry
        self.hwConfig = libConfig.HwConfig(defines.hwConfigFile, defaults = factory_defaults)
        self.hwConfig.logAllItems()
        self.config = libConfig.PrintConfig(self.hwConfig)

        from sl1fw.libHardware import Hardware
        self.hw = Hardware(self.hwConfig, self.config)

        from sl1fw.libInternet import Internet
        self.inet = Internet()

        if debugDisplay:
            devices = [debugDisplay]
        else:
            from sl1fw.libQtDisplay import QtDisplay
            qtdisplay = QtDisplay()

            from sl1fw.libWebDisplay import WebDisplay
            webdisplay = WebDisplay()

            devices = [qtdisplay, webdisplay]
        #endif

        from sl1fw.libScreen import Screen
        self.screen = Screen(self.hwConfig)

        from sl1fw.libPages import PageWait
        from sl1fw.pages.start import PageStart
        from sl1fw.libDisplay import Display
        self.display = Display(self.hwConfig, self.config, devices, self.hw, self.inet, self.screen)

        self.hw.connectMC(PageWait(self.display), PageStart(self.display))

        self.inet.startNetMonitor(self.display.assignNetActive)

        self.eventLoop = GLib.MainLoop()
        self.eventThread = threading.Thread(target=self.loopThread)
        self.eventThread.start()

        self.logger.info("Start time: %f secs", time() - startTime)
    #endclass


    def __del__(self):
        self.exit()
    #enddef


    def exit(self):
        self.running = False
        self.screen.exit()
        self.display.exit()
        self.inet.exit()
        self.hw.exit()
        self.eventLoop.quit()
    #enddef


    def start(self):
        from sl1fw.libExposure import Exposure
        firstRun = True

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
                    if not self.hwConfig.defaultsSet():
                        self.display.pages['error'].setParams(
                            text=_("Failed to load fans and LEDS factory calibration."))
                        self.display.doMenu("error")
                    #endif

                    if self.hwConfig.showUnboxing:
                        self.hw.beepRepeat(1)
                        self.display.doMenu("unboxing1")
                        sleep(0.5)
                    elif self.hwConfig.showWizard:
                        self.hw.beepRepeat(1)
                        self.display.doMenu("wizard1")
                        sleep(0.5)
                    #endif
                #endif

                self.display.pages['home'].readyBeep = True
                self.display.doMenu("home")
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

    #enddef

    def loopThread(self):
        self.logger.debug("Registering dbus event handlers")
        locale = SystemBus().get("org.freedesktop.locale1")
        locale.PropertiesChanged.connect(self.localeChanged)

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

#endclass
