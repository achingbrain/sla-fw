# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

from sl1fw.libPages import page, Page


@page
class PageFansLeds(Page):
    Name = "fansleds"

    def __init__(self, display):
        super(PageFansLeds, self).__init__(display)
        self.pageUI = "setup"
        self.pageTitle = N_("Fans & UV LED")
        self.autorepeat = {
                'minus2g1' : (5, 1), 'plus2g1' : (5, 1),
                'minus2g2' : (5, 1), 'plus2g2' : (5, 1),
                'minus2g3' : (5, 1), 'plus2g3' : (5, 1),
                'minus2g4' : (5, 1), 'plus2g4' : (5, 1),
                'minus2g5' : (5, 1), 'plus2g5' : (5, 1),
                'minus2g6' : (5, 1), 'plus2g6' : (5, 1),
                'minus2g7' : (5, 1), 'plus2g7' : (5, 1),
                'minus2g8' : (5, 1), 'plus2g8' : (5, 1),
                }
        self.items.update({
                'label1g1' : _("UV LED fan"),
                'label1g2' : _("Blower fan"),
                'label1g3' : _("Rear fan"),
                'label1g5' : _("UV LED"),
                'label1g7' : _("Trigger"),

                'label2g1' : _("UV LED fan PWM"),
                'label2g2' : _("Blower fan PWM"),
                'label2g3' : _("Rear fan PWM"),
                'label2g5' : _("UV LED PWM"),
                'label2g6' : _("UV calib. temperature"),
                'label2g7' : _("UV calib. intensity"),

                'button1' : _("Save defaults"),
                'button3' : _("Defaults"),
                'button4' : _("Save"),
                'back' : _("Back"),
                })
        self.updateDataPeriod = 0.5
        self.valuesToSave = list(('fan1pwm', 'fan2pwm', 'fan3pwm', 'uvpwm', 'uvcalibtemp', 'uvcalibintensity'))
        self.checkCooling = True
    #enddef


    def show(self):
        self.oldValues = {}
        self.changed = {}
        self.temp = {}
        self.temp['uvcalibtemp'] = self.display.hwConfig.uvCalibTemp
        self.temp['uvcalibintensity'] = self.display.hwConfig.uvCalibIntensity
        self.items['value2g6'] = self.temp['uvcalibtemp']
        self.items['value2g7'] = self.temp['uvcalibintensity']

        super(PageFansLeds, self).show()
    #enddef


    def updateData(self):
        items = {}
        self.temp['fs1'], self.temp['fs2'], self.temp['fs3'] = self.display.hw.getFans()
        self.temp['uls'] = self.display.hw.getUvLedState()[0]
        self.temp['cls'] = self.display.hw.getCameraLedState()
        self._setItem(items, self.oldValues, 'state1g1', self.temp['fs1'])
        self._setItem(items, self.oldValues, 'state1g2', self.temp['fs2'])
        self._setItem(items, self.oldValues, 'state1g3', self.temp['fs3'])
        self._setItem(items, self.oldValues, 'state1g5', self.temp['uls'])
        self._setItem(items, self.oldValues, 'state1g7', self.temp['cls'])

        self.temp['fan1pwm'], self.temp['fan2pwm'], self.temp['fan3pwm'] = self.display.hw.getFansPwm()
        self.temp['uvpwm'] = self.display.hw.getUvLedPwm()
        self._setItem(items, self.oldValues, 'value2g1', self.temp['fan1pwm'])
        self._setItem(items, self.oldValues, 'value2g2', self.temp['fan2pwm'])
        self._setItem(items, self.oldValues, 'value2g3', self.temp['fan3pwm'])
        self._setItem(items, self.oldValues, 'value2g5', self.temp['uvpwm'])

        if len(items):
            self.showItems(**items)
        #endif
    #enddef


    def button1ButtonRelease(self):
        self.display.pages['yesno'].setParams(
            yesFce = self.save_defaults,
            text = _("Save current values as factory defaults?"))
        return "yesno"
    #enddef


    def save_defaults(self):
        self._update_config()

        if not self.writeToFactory(self.saveDefaultsFile):
            self.display.pages['error'].setParams(
                text = _("!!! Failed to save factory defaults !!!"))
            return "error"
        #else

        return "_BACK_"
    #enddef


    def button3ButtonRelease(self):
        self.display.pages['yesno'].setParams(
            yesFce = self.reset_to_defaults,
            text = _("Reset to factory defaults?"))
        return "yesno"
    #enddef


    def reset_to_defaults(self):
        self.display.hwConfig.update(
            uvCurrent = None,   # remove old value too
            uvPwm = None,
            fan1Pwm = None,
            fan2Pwm = None,
            fan3Pwm = None,
        )
        self._reset_hw_values()
        if not self.display.hwConfig.writeFile():
            self.display.pages['error'].setParams(
                text = _("Cannot save configuration"))
            return "error"
        #endif
        return "_BACK_"
    #enddef


    def _update_config(self):
        # filter only wanted items
        filtered = { k : v for k, v in filter(lambda t: t[0] in self.valuesToSave, self.changed.items()) }
        self.display.hwConfig.update(**filtered)
    #enddef


    def button4ButtonRelease(self):
        ''' save '''
        self.display.hw.saveUvStatistics()
        self._update_config()
        if not self.display.hwConfig.writeFile():
            self.display.pages['error'].setParams(
                text = _("Cannot save configuration"))
            return "error"
        #endif
        return super(PageFansLeds, self).backButtonRelease()
    #endif


    def _reset_hw_values(self):
        self.display.hw.setFansPwm(
            (self.display.hwConfig.fan1Pwm,
             self.display.hwConfig.fan2Pwm,
             self.display.hwConfig.fan3Pwm))
        self.display.hw.setUvLedPwm(self.display.hwConfig.uvPwm)
    #enddef


    def backButtonRelease(self):
        self.display.hw.saveUvStatistics()
        self._reset_hw_values()
        return super(PageFansLeds, self).backButtonRelease()
    #enddef


    def state1g1ButtonRelease(self):
        self._onOff(self.temp, self.changed, 0, 'fs1')
        self.display.hw.setFans((self.temp['fs1'], self.temp['fs2'], self.temp['fs3']))
        self.display.hw.setFanCheckMask((self.temp['fs1'], self.temp['fs2'], self.temp['fs3']))
    #enddef


    def state1g2ButtonRelease(self):
        self._onOff(self.temp, self.changed, 1, 'fs2')
        self.display.hw.setFans((self.temp['fs1'], self.temp['fs2'], self.temp['fs3']))
        self.display.hw.setFanCheckMask((self.temp['fs1'], self.temp['fs2'], self.temp['fs3']))
    #enddef


    def state1g3ButtonRelease(self):
        self._onOff(self.temp, self.changed, 2, 'fs3')
        self.display.hw.setFans((self.temp['fs1'], self.temp['fs2'], self.temp['fs3']))
        self.display.hw.setFanCheckMask((self.temp['fs1'], self.temp['fs2'], self.temp['fs3']))
    #enddef


    def state1g5ButtonRelease(self):
        self._onOff(self.temp, self.changed, 4, 'uls')
        self.display.hw.uvLed(self.temp['uls'])
        if self.temp['uls']:
            self.display.hw.startFans()
        else:
            self.display.hw.stopFans()
        #endif
    #enddef


    def state1g7ButtonRelease(self):
        self._onOff(self.temp, self.changed, 6, 'cls')
        self.display.hw.cameraLed(self.temp['cls'])
    #enddef


    def minus2g1Button(self):
        self._value(self.temp, self.changed, 0, 'fan1pwm', 0, 100, -5)
        self.display.hw.setFansPwm((self.temp['fan1pwm'], self.temp['fan2pwm'], self.temp['fan3pwm']))
    #enddef


    def plus2g1Button(self):
        self._value(self.temp, self.changed, 0, 'fan1pwm', 0, 100, 5)
        self.display.hw.setFansPwm((self.temp['fan1pwm'], self.temp['fan2pwm'], self.temp['fan3pwm']))
    #enddef


    def minus2g2Button(self):
        self._value(self.temp, self.changed, 1, 'fan2pwm', 0, 100, -5)
        self.display.hw.setFansPwm((self.temp['fan1pwm'], self.temp['fan2pwm'], self.temp['fan3pwm']))
    #enddef


    def plus2g2Button(self):
        self._value(self.temp, self.changed, 1, 'fan2pwm', 0, 100, 5)
        self.display.hw.setFansPwm((self.temp['fan1pwm'], self.temp['fan2pwm'], self.temp['fan3pwm']))
    #enddef


    def minus2g3Button(self):
        self._value(self.temp, self.changed, 2, 'fan3pwm', 0, 100, -5)
        self.display.hw.setFansPwm((self.temp['fan1pwm'], self.temp['fan2pwm'], self.temp['fan3pwm']))
    #enddef


    def plus2g3Button(self):
        self._value(self.temp, self.changed, 2, 'fan3pwm', 0, 100, 5)
        self.display.hw.setFansPwm((self.temp['fan1pwm'], self.temp['fan2pwm'], self.temp['fan3pwm']))
    #enddef


    def minus2g5Button(self):
        self._value(self.temp, self.changed, 4, 'uvpwm', 0, 250, -1)
        self.display.hw.setUvLedPwm(self.temp['uvpwm'])
    #enddef


    def plus2g5Button(self):
        self._value(self.temp, self.changed, 4, 'uvpwm', 0, 250, 1)
        self.display.hw.setUvLedPwm(self.temp['uvpwm'])
    #enddef


    def minus2g6Button(self):
        self._value(self.temp, self.changed, 5, 'uvcalibtemp', 30, 50, -1)
    #enddef


    def plus2g6Button(self):
        self._value(self.temp, self.changed, 5, 'uvcalibtemp', 30, 50, 1)
    #enddef


    def minus2g7Button(self):
        self._value(self.temp, self.changed, 6, 'uvcalibintensity', 80, 200, -1)
    #enddef


    def plus2g7Button(self):
        self._value(self.temp, self.changed, 6, 'uvcalibintensity', 80, 200, 1)
    #enddef

#endclass
