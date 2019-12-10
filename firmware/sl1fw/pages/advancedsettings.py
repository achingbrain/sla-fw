# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw import defines
from sl1fw.libConfig import ConfigException
from sl1fw.pages.base import Page
from sl1fw.pages.wait import PageWait
from sl1fw.pages import page


def item_updater(str_func = None, minLimit = None):
    def new_decorator(func):
        def new_func(self, value):
            func(self, value)

            if minLimit is not None and value < minLimit:
                value = "OFF"
            elif str_func:
                value = str_func(getattr(self, func.__name__))
            else:
                value = getattr(self, func.__name__)
            #endif

            key = func.__name__
            self.showItems(**{key: value})
        #enddef
        return new_func
    #enddef
    return new_decorator
#enddef


def value_saturate(minimum, maximum):
    def new_decorator(func):
        def new_func(self, value):
            if not minimum <= value <= maximum:
                self.display.hw.beepAlarm(1)
                return
            else:
                func(self, value)
            #enddif
        #enddef
        return new_func
    #enddef
    return new_decorator
#enddef


def confirm_leave(func):
    def new_func(self):
        retc = self.confirmChanges()
        if retc:
            return retc
        else:
            return func(self)
        #endif
    #enddef
    return new_func
#enddef


@page
class PageAdvancedSettings(Page):
    Name = "advancedsettings"

    def __init__(self, display):
        super(PageAdvancedSettings, self).__init__(display)
        self.pageUI = "advancedsettings"
        self._display_test = False
        self.configwrapper = None
        self._calibTowerOffset_mm = None
        self.confirmReturnPending = False

        self.autorepeat = {
            'minus_tiltsensitivity': (5, 1), 'plus_tiltsensitivity': (5, 1),
            'minus_towersensitivity': (5, 1), 'plus_towersensitivity': (5, 1),
            'minus_fasttiltlimit': (5, 1), 'plus_fasttiltlimit': (5, 1),
            'minus_toweroffset': (5, 1), 'plus_toweroffset': (5, 1),
            'minus_rearfanspeed': (5, 1), 'plus_rearfanspeed': (5, 1),
        }
    #enddef


    @property
    def tilt_sensitivity(self):
        return self.configwrapper.tiltSensitivity
    #enddef

    @tilt_sensitivity.setter
    @value_saturate(-2, 2)
    @item_updater()
    def tilt_sensitivity(self, value):
        self.configwrapper.tiltSensitivity = value
    #enddef


    @property
    def tower_sensitivity(self):
        return self.configwrapper.towerSensitivity
    #enddef

    @tower_sensitivity.setter
    @value_saturate(-2, 2)
    @item_updater()
    def tower_sensitivity(self, value):
        self.configwrapper.towerSensitivity = value
    #enddef


    @property
    def fast_tilt_limit(self):
        return self.configwrapper.limit4fast
    #enddef

    @fast_tilt_limit.setter
    @value_saturate(0, 100)
    @item_updater()
    def fast_tilt_limit(self, value):
        self.configwrapper.limit4fast = value
    #enddef


    @property
    def tower_offset(self):
        if self._calibTowerOffset_mm is None:
            self._calibTowerOffset_mm = self.display.hwConfig.calcMM(self.configwrapper.calibTowerOffset)
        #endif
        return self._calibTowerOffset_mm
    #enddef

    @tower_offset.setter
    @value_saturate(-0.5, 0.5)
    @item_updater(str_func=lambda x: "%+.3f" % x)
    def tower_offset(self, value):
        self._calibTowerOffset_mm = value
        self.configwrapper.calibTowerOffset = self.display.hwConfig.calcMicroSteps(value)
    #enddef


    @property
    def rear_fan_speed(self):
        return self.configwrapper.fan3Rpm
    #enddef

    @rear_fan_speed.setter
    @value_saturate(400, 5000)
    @item_updater(minLimit = defines.fanMinRPM)
    def rear_fan_speed(self, value):
        self.configwrapper.fan3Rpm = value
        self.display.hw.setFansRpm({ 2 : self.configwrapper.fan3Rpm })
        self.display.hw.setFans({ 2 : True })
    #enddef


    @property
    def auto_power_off(self):
        return self.configwrapper.autoOff
    #enddef

    @auto_power_off.setter
    @item_updater()
    def auto_power_off(self, value):
        self.configwrapper.autoOff = value
    #enddef


    @property
    def cover_check(self):
        return self.configwrapper.coverCheck
    #enddef

    @cover_check.setter
    @item_updater()
    def cover_check(self, value):
        self.configwrapper.coverCheck = value
    #enddef


    @property
    def resin_sensor(self):
        return self.configwrapper.resinSensor
    #enddef

    @resin_sensor.setter
    @item_updater()
    def resin_sensor(self, value):
        self.configwrapper.resinSensor = value
    #enddef


    def show(self):
        if self.configwrapper is None or not self.confirmReturnPending:
            self.configwrapper = self.display.hwConfig.get_writer()
        else:
            self.confirmReturnPending = False
        #endif
        self._calibTowerOffset_mm = None

        self.items.update({
            'showAdmin': self.display.show_admin,  # TODO: Remove once client uses show_admin
            'show_admin': self.display.show_admin,
            'tilt_sensitivity': self.tilt_sensitivity,
            'tower_sensitivity': self.tower_sensitivity,
            'fast_tilt_limit': self.fast_tilt_limit,
            'tower_offset': "%+.3f" % self.tower_offset,
            'rear_fan_speed': self.rear_fan_speed if self.rear_fan_speed >= defines.fanMinRPM else "OFF",
            'auto_power_off': self.auto_power_off,
            'cover_check': self.cover_check,
            'resin_sensor': self.resin_sensor,
        })
        super(PageAdvancedSettings, self).show()
    #enddef


    # Move platform
    @confirm_leave
    def towermoveButtonRelease(self):
        return "towermove"
    #enddef


    # Move resin tank
    @confirm_leave
    def tiltmoveButtonRelease(self):
        return "tiltmove"
    #enddef


    # Time settings
    @confirm_leave
    def timesettingsButtonRelease(self):
        return "timesettings"
    #enddef


    # Change language (TODO: Not in the graphical design, not yet implemented properly)
    @confirm_leave
    def setlanguageButtonRelease(self):
        return "setlanguage"
    #enddef


    # Hostname
    @confirm_leave
    def sethostnameButtonRelease(self):
        return "sethostname"
    #enddef


    # Change name/password
    @confirm_leave
    def setremoteaccessButtonRelease(self):
        return "setlogincredentials"
    #enddef


    # Tilt sensitivity
    def minus_tiltsensitivityButton(self):
        self.tilt_sensitivity -= 1
    #enddef
    def plus_tiltsensitivityButton(self):
        self.tilt_sensitivity += 1
    #enddef


    # Tower sensitivity
    def minus_towersensitivityButton(self):
        self.tower_sensitivity -= 1
    # enddef
    def plus_towersensitivityButton(self):
        self.tower_sensitivity += 1
    # enddef


    # Limit for fast tilt
    def minus_fasttiltlimitButton(self):
        self.fast_tilt_limit -= 1
    #enddef
    def plus_fasttiltlimitButton(self):
        self.fast_tilt_limit += 1
    #enddef


    # Tower offset
    # TODO: Adjust in mm, compute steps
    # Currently we are adjusting steps, but showing mm. This in counterintuitive.
    def minus_toweroffsetButton(self):
        self.tower_offset -= 0.001
    #enddef
    def plus_toweroffsetButton(self):
        self.tower_offset += 0.001
    #enddef


    # Display test
    @confirm_leave
    def displaytestButtonRelease(self):
        self.display.pages['confirm'].setParams(
            continueFce = self.displaytestContinue,
            pageTitle = _("Display test"),
            imageName = "selftest-remove_tank.jpg",
            text = _("Please unscrew and remove the resin tank."))
        return "confirm"
    #enddef


    def displaytestContinue(self):
        self.display.pages['confirm'].setParams(
            continueFce = self.displaytest,
            pageTitle = _("Display test"),
            imageName = "close_cover_no_tank.jpg",
            text = _("Please close the orange lid."))
        return "confirm"
    #enddef


    def displaytest(self):
        return "displaytest"
    #endif

    # Rear fan speed
    def minus_rearfanspeedButton(self):
        self.rear_fan_speed -= 100
    #enddef
    def plus_rearfanspeedButton(self):
        self.rear_fan_speed += 100
    #enddef


    # Auto power off
    def autopoweroffButtonRelease(self):
        self.auto_power_off = not self.auto_power_off
    #enddef


    # Cover check
    def covercheckButtonRelease(self):
        if self.cover_check:
            self.display.pages['yesno'].setParams(
                yesFce = self.disableCoverCheck,
                noFce = self._doConfirmReturn,
                text = _("Disable the cover sensor?\n"
                       "\n"
                       "CAUTION: This may lead to unwanted exposure to UV light. This action is not recommended!"))
            return "yesno"
        else:
            self.cover_check = True
        #endif
    #enddef


    def disableCoverCheck(self):
        self.cover_check = False
        return self._doConfirmReturn()
    #enddef


    def _doConfirmReturn(self):
        self.confirmReturnPending = True
        return "_BACK_"
    #enddef


    # Resin Sensor
    def resinsensorButtonRelease(self):
        if self.resin_sensor:
            self.display.pages['yesno'].setParams(
                yesFce = self.disableResinSensor,
                noFce = self._doConfirmReturn,
                text = _("Disable the resin sensor?\n"
                       "\n"
                       "CAUTION: This may lead to failed prints or resin tank overflow! This action is not recommended!"))
            return "yesno"
        else:
            self.resin_sensor = True
        #endif
    #enddef


    def disableResinSensor(self):
        self.resin_sensor = False
        return self._doConfirmReturn()
    #enddef


    # Firmware update
    @confirm_leave
    def firmwareupdateButtonRelease(self):
        return "firmwareupdate"
    #enddef


    # Download examples
    @confirm_leave
    def downloadexamplesButtonRelease(self):
        pageWait = PageWait(self.display)
        pageWait.show()
        try:
            self.display.inet.download_examples(page=pageWait, cpu_serial_no=self.display.hw.cpuSerialNo)
            return "_BACK_"
        except Exception as e:
            self.display.pages['error'].setParams(
                    text = _("Fetching of samples failed") + str(e))
            return "error"
        #endtry
    #enddef


    # Factory reset
    @confirm_leave
    def factoryresetButtonRelease(self):
        return "factoryreset"
    #enddef


    # Admin
    @confirm_leave
    def adminButtonRelease(self):
        if self.display.show_admin:
            return "admin"
        #endif
    #enddef


    # Logs export to usb
    def exportlogstoflashdiskButtonRelease(self):
        return self.saveLogsToUSB()
    #enddef


    # Show wizard
    @confirm_leave
    def wizardButtonRelease(self):
        return "wizardinit"
    #enddef


    @confirm_leave
    def backButtonRelease(self):
        return super(PageAdvancedSettings, self).backButtonRelease()
    #enddef


    def confirmChanges(self):
        self.display.hw.setFans({ 2 : False })
        if self.configwrapper.changed():
            self.display.pages['yesno'].setParams(
                    pageTitle = N_("Save changes?"),
                    text = _("Save changes?"))
            if self.display.doMenu("yesno"):
                # save changes
                sensitivity_changed = self.configwrapper.changed('towersensitivity') or self.configwrapper.changed('tiltsensitivity')
                try:
                    self.configwrapper.commit()
                except ConfigException:
                    self.logger.exception("Failed to save configuration")
                    self.display.pages['error'].setParams(
                        text = _("Cannot save configuration"))
                    return "error"
                #endif
                if sensitivity_changed:
                    self.logger.info("Motor sensitivity changed. Updating profiles.")
                    self.display.hw.updateMotorSensitivity(self.display.hwConfig.tiltSensitivity, self.display.hwConfig.towerSensitivity)
                #endif
            else:
                # discard changes
                self.display.hw.setFansRpm({ 2 : self.display.hwConfig.fan3Rpm })
            #endif
        #endif
    #enddef

#endclass
