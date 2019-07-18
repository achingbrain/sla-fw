# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

from sl1fw import defines
from sl1fw.libConfig import ConfigException
from sl1fw.libPages import Page
from sl1fw.pages import page


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

                'label2g1' : _("UV LED fan RPM"),
                'label2g2' : _("Blower fan RPM"),
                'label2g3' : _("Rear fan RPM"),
                'label2g5' : _("UV LED PWM"),
                'label2g6' : _("UV calib. warm-up [s]"),
                'label2g7' : _("UV calib. intensity"),
                'label2g8' : _("UV cal. min. int. edge"),

                'button1' : _("Save defaults"),
                'button3' : _("Defaults"),
                'button4' : _("Save"),
                'back' : _("Back"),
                })
        self.updateDataPeriod = 0.5
        self.valuesToSave = list(('fan1rpm', 'fan2rpm', 'fan3rpm', 'uvpwm', 'uvwarmuptime', 'uvcalibintensity', 'uvcalibminintedge'))
        self.checkCooling = True
    #enddef


    def show(self):
        self.oldValues = {}
        self.changed = {}
        self.temp = {}
        self.temp['uvwarmuptime'] = self.display.hwConfig.uvWarmUpTime
        self.temp['uvcalibintensity'] = self.display.hwConfig.uvCalibIntensity
        self.temp['uvcalibminintedge'] = self.display.hwConfig.uvCalibMinIntEdge
        self.items['value2g6'] = self.temp['uvwarmuptime']
        self.items['value2g7'] = self.temp['uvcalibintensity']
        self.items['value2g8'] = self.temp['uvcalibminintedge']

        self.temp['fan1rpm'] = self.display.hwConfig.fan1Rpm
        self.temp['fan2rpm'] = self.display.hwConfig.fan2Rpm
        self.temp['fan3rpm'] = self.display.hwConfig.fan3Rpm
        self.items['value2g1'] = str(self.temp['fan1rpm'])
        self.items['value2g2'] = str(self.temp['fan2rpm'])
        self.items['value2g3'] = str(self.temp['fan3rpm']) if self.temp['fan3rpm'] >= defines.fanMinRPM else "OFF"

        super(PageFansLeds, self).show()
    #enddef


    def updateData(self):
        items = {}
        fans = self.display.hw.getFans()
        self.temp['fs1'], self.temp['fs2'], self.temp['fs3'] = fans[0], fans[1], fans[2]
        self.temp['uls'] = self.display.hw.getUvLedState()[0]
        self.temp['cls'] = self.display.hw.getCameraLedState()
        self._setItem(items, self.oldValues, 'state1g1', self.temp['fs1'])
        self._setItem(items, self.oldValues, 'state1g2', self.temp['fs2'])
        self._setItem(items, self.oldValues, 'state1g3', self.temp['fs3'])
        self._setItem(items, self.oldValues, 'state1g5', self.temp['uls'])
        self._setItem(items, self.oldValues, 'state1g7', self.temp['cls'])

        self.temp['uvpwm'] = self.display.hw.uvLedPwm
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
        del self.display.hwConfig.uvCurrent   # remove old value too
        del self.display.hwConfig.uvPwm
        del self.display.hwConfig.fan1Rpm
        del self.display.hwConfig.fan2Rpm
        del self.display.hwConfig.fan3Rpm
        self._reset_hw_values()
        try:
            self.display.hwConfig.write()
        except ConfigException:
            self.logger.exception("Cannot save configuration")
            self.display.pages['error'].setParams(
                text = _("Cannot save configuration"))
            return "error"
        #endtry
        return "_BACK_"
    #enddef


    def _update_config(self):
        # filter only wanted items
        filtered = { k : v for k, v in [t for t in self.changed.items() if t[0] in self.valuesToSave] }
        if 'uvpwm' in filtered:
            del self.display.hwConfig.uvCurrent   # remove old value too
        #enddef
        self.display.hwConfig.get_writer().commit_dict(filtered)
    #enddef


    def button4ButtonRelease(self):
        ''' save '''
        self.display.hw.saveUvStatistics()
        self._update_config()
        try:
            self.display.hwConfig.write()
        except ConfigException:
            self.logger.exception("Cannot save configuration")
            self.display.pages['error'].setParams(
                text=_("Cannot save configuration"))
            return "error"
        # endtry
        return super(PageFansLeds, self).backButtonRelease()
    #endif


    def _reset_hw_values(self):
        self.display.hw.setFansRpm({
            0 : self.display.hwConfig.fan1Rpm,
            1 : self.display.hwConfig.fan2Rpm,
            2 : self.display.hwConfig.fan3Rpm,
            })
        self.display.hw.uvLedPwm = self.display.hwConfig.uvPwm
    #enddef


    def backButtonRelease(self):
        self.display.hw.saveUvStatistics()
        self._reset_hw_values()
        return super(PageFansLeds, self).backButtonRelease()
    #enddef


    def state1g1ButtonRelease(self):
        self._onOff(self.temp, self.changed, 0, 'fs1')
        self.display.hw.setFans({ 0 : self.temp['fs1'] })
        self.display.fanErrorOverride = False
        self.oldValues['state1g1'] = self.temp['fs1']
    #enddef


    def state1g2ButtonRelease(self):
        self._onOff(self.temp, self.changed, 1, 'fs2')
        self.display.hw.setFans({ 1: self.temp['fs2'] })
        self.display.fanErrorOverride = False
        self.oldValues['state1g2'] = self.temp['fs2']
    #enddef


    def state1g3ButtonRelease(self):
        self._onOff(self.temp, self.changed, 2, 'fs3')
        self.display.hw.setFans({ 2 : self.temp['fs3'] })
        self.display.fanErrorOverride = False
        self.oldValues['state1g3'] = self.temp['fs3']
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
        self._value(self.temp, self.changed, 0, 'fan1rpm', 500, 3000, -100)
        self.display.hw.setFansRpm({ 0 : self.temp['fan1rpm'] })
    #enddef


    def plus2g1Button(self):
        self._value(self.temp, self.changed, 0, 'fan1rpm', 500, 3000, 100)
        self.display.hw.setFansRpm({ 0 : self.temp['fan1rpm'] })
    #enddef


    def minus2g2Button(self):
        self._value(self.temp, self.changed, 1, 'fan2rpm', 500, 3700, -100)
        self.display.hw.setFansRpm({ 1: self.temp['fan2rpm'] })
    #enddef


    def plus2g2Button(self):
        self._value(self.temp, self.changed, 1, 'fan2rpm', 500, 3700, 100)
        self.display.hw.setFansRpm({ 1: self.temp['fan2rpm'] })
    #enddef


    def minus2g3Button(self):
        self._value(self.temp, self.changed, 2, 'fan3rpm', 400, 5000, -100, minLimit = defines.fanMinRPM)
        self.display.hw.setFansRpm({ 2 : self.temp['fan3rpm'] })
    #enddef


    def plus2g3Button(self):
        self._value(self.temp, self.changed, 2, 'fan3rpm', 400, 5000, 100, minLimit = defines.fanMinRPM)
        self.display.hw.setFansRpm({ 2 : self.temp['fan3rpm'] })
    #enddef


    def minus2g5Button(self):
        self._value(self.temp, self.changed, 4, 'uvpwm', 0, 250, -1)
        self.display.hw.uvLedPwm = self.temp['uvpwm']
    #enddef


    def plus2g5Button(self):
        self._value(self.temp, self.changed, 4, 'uvpwm', 0, 250, 1)
        self.display.hw.uvLedPwm = self.temp['uvpwm']
    #enddef


    def minus2g6Button(self):
        self._value(self.temp, self.changed, 5, 'uvwarmuptime', 0, 300, -1)
    #enddef


    def plus2g6Button(self):
        self._value(self.temp, self.changed, 5, 'uvwarmuptime', 0, 300, 1)
    #enddef


    def minus2g7Button(self):
        self._value(self.temp, self.changed, 6, 'uvcalibintensity', 80, 200, -1)
    #enddef


    def plus2g7Button(self):
        self._value(self.temp, self.changed, 6, 'uvcalibintensity', 80, 200, 1)
    #enddef


    def minus2g8Button(self):
        self._value(self.temp, self.changed, 7, 'uvcalibminintedge', 80, 200, -1)
    #enddef


    def plus2g8Button(self):
        self._value(self.temp, self.changed, 7, 'uvcalibminintedge', 80, 200, 1)
    #enddef

#endclass
