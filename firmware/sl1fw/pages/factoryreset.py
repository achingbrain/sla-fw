# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import os
from time import sleep

import pydbus

from sl1fw import defines
from sl1fw import libConfig
from sl1fw.display_state import DisplayState
from sl1fw.functions.system import shut_down
from sl1fw.libConfig import ConfigException
from sl1fw.pages import page
from sl1fw.pages.base import Page
from sl1fw.pages.wait import PageWait


@page
class PageFactoryReset(Page):
    Name = "factoryreset"

    NETWORK_MANAGER = "org.freedesktop.NetworkManager"

    def __init__(self, display):
        super(PageFactoryReset, self).__init__(display)
        self.pageUI = "yesno"
        self.pageTitle = N_("Are you sure?")
        self.checkPowerbutton = False
    #enddef


    def show(self):
        self.items.update({
            'text' : _("Do you really want to perform the factory reset?\n\n"
                "All settings will be erased!")})
        super(PageFactoryReset, self).show()
    #enddef


    def yesButtonRelease(self):
        self.display.state = DisplayState.FACTORY_RESET
        # http://www.wavsource.com/snds_2018-06-03_5106726768923853/movie_stars/schwarzenegger/erased.wav
        pageWait = PageWait(self.display, line1 = _("Relax... You've been erased."))
        pageWait.show()

        try:
            self.display.hwConfig.factory_reset()
            # do not display unpacking after user factory reset
            if not self.display.runtime_config.factory_mode:
                self.display.hwConfig.showUnboxing = False
            #endif
            self.display.hwConfig.write()
        except ConfigException:
            self.logger.exception("Failed to do factory reset on config")
            self.display.pages['error'].setParams(
                text=_("Cannot save factory defaults configuration"))
            return "error"
        #endif

        # erase MC EEPROM
        self.display.hw.eraseEeprom()

        # set homing profiles to factory defaults
        self.display.hw.updateMotorSensitivity(self.display.hwConfig.tiltSensitivity, self.display.hwConfig.towerSensitivity)

        system_bus = pydbus.SystemBus()

        # Reset hostname
        try:
            hostnamectl = system_bus.get("org.freedesktop.hostname1")
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
            self.logger.info("Factory reset: resetting networking settings")
            nm_settings = system_bus.get(self.NETWORK_MANAGER, "Settings")
            for item in nm_settings.ListConnections():
                try:
                    self.logger.info("Removing connection %s", item)
                    con = system_bus.get(self.NETWORK_MANAGER, item)
                    con.Delete()
                except:
                    self.logger.exception("Failed to delete connection %s", item)
        except:
            self.logger.exception("Failed to reset wifi config")
        #endtry

        # Reset timezone
        try:
            timedate = system_bus.get("org.freedesktop.timedate1")
            timedate.SetTimezone("Universal", False)
        except:
            self.logger.exception("Failed to reset timezone")
        #endtry

        # Reset locale
        try:
            locale = system_bus.get("org.freedesktop.locale1")
            locale.SetLocale(["C"], False)
        except:
            self.logger.exception("Setting locale failed")
        #endtry

        # Reset user UV calibration data
        try:
            os.remove(defines.uvCalibDataPath)
        except:
            self.logger.exception("Failed to remove user UV calibration data")
        #endtry

        # remove downloaded slicer profiles
        try:
            os.remove(defines.slicerProfilesFile)
        except:
            self.logger.exception("Failed to remove remove downloaded slicer profiles")
        #endtry

        # continue only in factory mode
        if not self.display.runtime_config.factory_mode:
            shut_down(self.display.hw, reboot=True)
            return
        #endif

        # disable factory mode
        self.writeToFactory(self._disableFactory)

        # do not do packing moves for kit
        if self.display.hw.isKit:
            shut_down(self.display.hw)
            return
        #endif

        pageWait.showItems(line1 = _("Printer is being set to packing positions"))
        self.display.hw.towerSync()
        self.display.hw.tiltSyncWait(retries = 3)
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

        shut_down(self.display.hw)
    #enddef


    # FIXME - to Page()
    def noButtonRelease(self):
        return self.backButtonRelease()
    #enddef


    def _disableFactory(self):
        if not libConfig.TomlConfig(defines.factoryConfigFile).save(data = { 'factoryMode': False }):
            self.logger.error("Factory mode was not disabled!")
        #endif
    #enddef

#endclass
