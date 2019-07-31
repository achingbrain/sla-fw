# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import os
from time import sleep
import toml
import pydbus

from sl1fw import defines
from sl1fw import libConfig
from sl1fw.libPages import page, Page, PageWait


@page
class PageFactoryReset(Page):
    Name = "factoryreset"

    def __init__(self, display):
        super(PageFactoryReset, self).__init__(display)
        self.pageUI = "yesno"
        self.pageTitle = N_("Are you sure?")
        self.checkPowerbutton = False
    #enddef


    def show(self):
        self.items.update({
            'text' : _("Do you really want to perform the factory reset?\n\n"
                "All settings will be deleted!")})
        super(PageFactoryReset, self).show()
    #enddef


    def yesButtonRelease(self):
        inFactoryMode = self.display.hwConfig.factoryMode
        try:
            with open(defines.hwConfigFactoryDefaultsFile, "r") as factory:
                factory_defaults = toml.load(factory)
            #endwith
        except:
            self.logger.exception("Failed to load factory defaults")
            factory_defaults = {}
        #endtry
        self.display.hwConfig = libConfig.HwConfig(defaults=factory_defaults)
        if not self.display.hwConfig.writeFile(filename=defines.hwConfigFile):
            self.display.pages['error'].setParams(
                text=_("Cannot save factory defaults configuration"))
            return "error"
        #endif

        # Reset hostname
        try:
            hostnamectl = pydbus.SystemBus().get("org.freedesktop.hostname1")
            hostname = "prusa64-sl1"
            hostnamectl.SetStaticHostname(hostname, False)
            hostnamectl.SetHostname(hostname, False)
        except:
            self.logger.exception("Failed to set hostname to factory default")
        #endtry

        # Reset apikey (will be regenerated on next boot)
        try:
            os.remove(defines.apikeyFile)
        except:
            self.logger.exception("Failed to remove api.key")
        #endtry

        # Reset wifi
        try:
            wificonfig = pydbus.SystemBus().get('cz.prusa3d.sl1.wificonfig')
            wificonfig.Reset()
        except:
            self.logger.exception("Failed to reset wifi config")
        #endtry

        # Reset timezone
        try:
            timedate = pydbus.SystemBus().get("org.freedesktop.timedate1")
            timedate.SetTimezone("Universal", False)
        except:
            self.logger.exception("Failed to reset timezone")
        #endtry

        # continue only in factory mode
        if not inFactoryMode:
            self.display.shutDown(doShutDown=True, reboot=True)
            return
        #endif

        # disable factory mode
        self.writeToFactory(self._disableFactory)

        pageWait = PageWait(self.display, line1 = _("Printer is being set to packing positions"))
        pageWait.show()
        self.display.hw.towerSync()
        self.display.hw.tiltSyncWait(3)
        while not self.display.hw.isTowerSynced():
            sleep(0.25)
        #endwhile

        # move tilt and tower to packing position
        self.display.hw.setTiltProfile('homingFast')
        self.display.hw.tiltMoveAbsolute(defines.defaultTiltHeight)
        while self.display.hw.isTiltMoving():
            sleep(0.25)
        #endwhile
        self.display.hw.setTowerProfile('homingFast')
        self.display.hw.towerMoveAbsolute(
            self.display.hwConfig.towerHeight - self.display.hwConfig.calcMicroSteps(74))
        while self.display.hw.isTowerMoving():
            sleep(0.25)
        #endwhile

        # at this height may be screwed down tank and inserted protective foam
        self.display.pages['confirm'].setParams(
            continueFce = self.factoryResetStep2,
            text = _("Insert protective foam"))
        return "confirm"
    #enddef


    def factoryResetStep2(self):
        pageWait = PageWait(self.display, line1 = _("Printer is being set to packing positions"))
        pageWait.show()

        # slightly press the foam against printers base
        self.display.hw.towerMoveAbsolute(
            self.display.hwConfig.towerHeight - self.display.hwConfig.calcMicroSteps(93))
        while self.display.hw.isTowerMoving():
            sleep(0.25)
        #endwhile

        self.display.shutDown(True)
    #enddef


    # FIXME - to Page()
    def noButtonRelease(self):
        return self.backButtonRelease()
    #enddef


    def _disableFactory(self):
        with open(defines.factoryConfigFile, "w") as f:
            toml.dump({
                'factoryMode': False
            }, f)
        #endwith
    #enddef

#endclass
