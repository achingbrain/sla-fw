# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# TODO: Fix following pylint problems
# pylint: disable=inconsistent-return-statements
# pylint: disable=too-many-public-methods

import os
from pathlib import Path
import subprocess

from sl1fw import defines
from sl1fw.errors.exceptions import ConfigException
from sl1fw.pages.base import Page
from sl1fw.pages import page


class PageSetup(Page):

    def __init__(self, display):
        super(PageSetup, self).__init__(display)
        self.pageUI = "setup"
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
        self.changed = {}
    #enddef


    def show(self):
        self.items.update({
                'button1' : "Export",
                'button2' : "Import",
                'button4' : "Save",
                })
        super(PageSetup, self).show()
    #enddef


    def button1ButtonRelease(self):
        ''' export '''
        savepath = self.getSavePath()
        if savepath is None:
            self.display.pages['error'].setParams(
                text="No USB storage present")
            return "error"
        #endif

        config_file = Path(savepath) / defines.hwConfigFileName

        try:
            subprocess.check_call(["usbremount", config_file])
            self.display.hwConfig.write(file_path=config_file)
        except ConfigException:
            self.logger.exception("Cannot save configuration")
            self.display.pages['error'].setParams(
                text = "Cannot save configuration")
            return "error"
        #endtry
    #enddef


    def button2ButtonRelease(self):
        ''' import '''
        savepath = self.getSavePath()
        if savepath is None:
            self.display.pages['error'].setParams(
                text="No USB storage present")
            return "error"
        #endif

        config_file = Path(savepath) / defines.hwConfigFileName

        if not os.path.isfile(config_file):
            self.display.pages['error'].setParams(
                text="Cannot find configuration to import")
            return "error"
        #endif

        try:
            self.display.hwConfig.read_file(config_file)
        except Exception:
            self.logger.exception("import exception:")
            self.display.pages['error'].setParams(
                text="Cannot import configuration")
            return "error"
        #endtry

        # TODO: Does import also means also save? There is special button for it.
        try:
            self.display.hwConfig.write()
        except ConfigException:
            self.logger.exception("Cannot save configuration")
            self.display.pages['error'].setParams(
                text = "Cannot save configuration")
            return "error"
        #endtry

        self.show()
    #enddef


    def button4ButtonRelease(self):
        """
        Save

        :return: None
        """
        try:
            self.display.hwConfig.get_writer().commit_dict(self.changed)
        except ConfigException:
            self.logger.exception("Cannot save configuration")
            self.display.pages['error'].setParams(
                text="Cannot save configuration")
            return "error"
        #endtry
        return super(PageSetup, self).backButtonRelease()
    #endif
#enddef


@page
class PageSetupHw(PageSetup):
    Name = "setuphw"

    def __init__(self, display):
        super(PageSetupHw, self).__init__(display)
        self.pageTitle = "Hardware Setup"
        self.temp = {}
    #enddef


    def show(self):
        self.items.update({
                'label1g1' : "Fan check",
                'label1g2' : "Cover check",
                'label1g3' : "MC version check",
                'label1g4' : "Use resin sensor",
                'label1g5' : "Auto power off",
                'label1g6' : "Mute (no beeps)",

                'label2g1' : "Screw [mm/rot]",
                'label2g2' : "Tilt msteps",
                'label2g3' : "Measuring moves count",
                'label2g4' : "Stirring moves count",
                'label2g5' : "Delay after stirring [s]",
                'label2g6' : "Power LED intensity",
                'label2g7' : "UV cal. boost toler.",
                'label2g8' : "MC board version",
                })
        self.changed = {}
        self.temp = {}
        self.temp['screwmm'] = self.display.hwConfig.screwMm
        self.temp['tiltheight'] = self.display.hwConfig.tiltHeight
        self.temp['calibtoweroffset'] = self.display.hwConfig.calibTowerOffset
        self.temp['measuringmoves'] = self.display.hwConfig.measuringMoves
        self.temp['stirringmoves'] = self.display.hwConfig.stirringMoves
        self.temp['stirringdelay'] = self.display.hwConfig.stirringDelay
        self.temp['pwrledpwm'] = self.display.hwConfig.pwrLedPwm
        self.temp['uvcalibboosttolerance'] = self.display.hwConfig.uvCalibBoostTolerance
        self.temp['mcboardversion'] = self.display.hwConfig.MCBoardVersion

        self.items['value2g1'] = str(self.temp['screwmm'])
        self.items['value2g2'] = str(self.temp['tiltheight'])
        self.items['value2g3'] = str(self.temp['measuringmoves'])
        self.items['value2g4'] = str(self.temp['stirringmoves'])
        self.items['value2g5'] = self._strTenth(self.temp['stirringdelay'])
        self.items['value2g6'] = str(self.temp['pwrledpwm'])
        self.items['value2g7'] = str(self.temp['uvcalibboosttolerance'])
        self.items['value2g8'] = str(self.temp['mcboardversion'])

        self.temp['fancheck'] = self.display.hwConfig.fanCheck
        self.temp['covercheck'] = self.display.hwConfig.coverCheck
        self.temp['mcversioncheck'] = self.display.hwConfig.MCversionCheck
        self.temp['resinsensor'] = self.display.hwConfig.resinSensor
        self.temp['autooff'] = self.display.hwConfig.autoOff
        self.temp['mute'] = self.display.hwConfig.mute

        self.items['state1g1'] = int(self.temp['fancheck'])
        self.items['state1g2'] = int(self.temp['covercheck'])
        self.items['state1g3'] = int(self.temp['mcversioncheck'])
        self.items['state1g4'] = int(self.temp['resinsensor'])
        self.items['state1g5'] = int(self.temp['autooff'])
        self.items['state1g6'] = int(self.temp['mute'])

        super(PageSetupHw, self).show()
    #enddef


    def state1g1ButtonRelease(self):
        self._onOff(self.temp, self.changed, 0, 'fancheck')
    #enddef


    def state1g2ButtonRelease(self):
        self._onOff(self.temp, self.changed, 1, 'covercheck')
    #enddef


    def state1g3ButtonRelease(self):
        self._onOff(self.temp, self.changed, 2, 'mcversioncheck')
    #enddef


    def state1g4ButtonRelease(self):
        self._onOff(self.temp, self.changed, 3, 'resinsensor')
    #enddef


    def state1g5ButtonRelease(self):
        self._onOff(self.temp, self.changed, 4, 'autooff')
    #enddef


    def state1g6ButtonRelease(self):
        self._onOff(self.temp, self.changed, 5, 'mute')
    #enddef


    def minus2g1Button(self):
        self._value(self.temp, self.changed, 0, 'screwmm', 2, 8, -1)
    #enddef


    def plus2g1Button(self):
        self._value(self.temp, self.changed, 0, 'screwmm', 2, 8, 1)
    #enddef


    def minus2g2Button(self):
        self._value(self.temp, self.changed, 1, 'tiltheight', 1, 6000, -1)
    #enddef


    def plus2g2Button(self):
        self._value(self.temp, self.changed, 1, 'tiltheight', 1, 6000, 1)
    #enddef


    def minus2g3Button(self):
        self._value(self.temp, self.changed, 2, 'measuringmoves', 1, 10, -1)
    #enddef


    def plus2g3Button(self):
        self._value(self.temp, self.changed, 2, 'measuringmoves', 1, 10, 1)
    #enddef


    def minus2g4Button(self):
        self._value(self.temp, self.changed, 3, 'stirringmoves', 1, 10, -1)
    #enddef


    def plus2g4Button(self):
        self._value(self.temp, self.changed, 3, 'stirringmoves', 1, 10, 1)
    #enddef


    def minus2g5Button(self):
        self._value(self.temp, self.changed, 4, 'stirringdelay', 0, 300, -5, self._strTenth)
    #enddef


    def plus2g5Button(self):
        self._value(self.temp, self.changed, 4, 'stirringdelay', 0, 300, 5, self._strTenth)
    #enddef


    def minus2g6Button(self):
        self._value(self.temp, self.changed, 5, 'pwrledpwm', 0, 100, -5)
        self.display.hw.powerLedPwm = self.temp['pwrledpwm']
    #enddef


    def plus2g6Button(self):
        self._value(self.temp, self.changed, 5, 'pwrledpwm', 0, 100, 5)
        self.display.hw.powerLedPwm = self.temp['pwrledpwm']
    #enddef


    def minus2g7Button(self):
        self._value(self.temp, self.changed, 6, 'uvcalibboosttolerance', 0, 100, -1)
    #enddef


    def plus2g7Button(self):
        self._value(self.temp, self.changed, 6, 'uvcalibboosttolerance', 0, 100, 1)
    #enddef


    def minus2g8Button(self):
        self._value(self.temp, self.changed, 7, 'mcboardversion', 5, 6, -1)
    #enddef


    def plus2g8Button(self):
        self._value(self.temp, self.changed, 7, 'mcboardversion', 5, 6, 1)
    #enddef


    def backButtonRelease(self):
        self.display.hw.powerLedPwm = self.display.hwConfig.pwrLedPwm
        return super(PageSetupHw, self).backButtonRelease()
    #enddef

#endclass


@page
class PageSetupExposure(PageSetup):
    Name = "setupexpo"

    def __init__(self, display):
        super(PageSetupExposure, self).__init__(display)
        self.pageTitle = "Exposure Setup"
        self.temp = {}
    #enddef


    def show(self):
        self.items.update({
                'label1g1' : "Blink exposure",
                'label1g2' : "Per-Partes expos.",
                'label1g3' : "Use tilt",
                'label1g4' : "Up&down UV on",

                'label2g1' : "Layer trigger [s]",
                'label2g2' : "Layer tower hop [mm]",
                'label2g3' : "Delay before expos. [s]",
                'label2g4' : "Delay after expos. [s]",
                'label2g5' : "Up&down wait [s]",
                'label2g6' : "Up&down every n-th l.",
                'label2g7' : "Up&down Z offset [mm]",
                'label2g8' : "Up&down expo comp [s]",
                })
        self.changed = {}
        self.temp = {}
        self.temp['trigger'] = self.display.hwConfig.trigger
        self.temp['limit4fast'] = self.display.hwConfig.limit4fast
        self.temp['layertowerhop'] = self.display.hwConfig.layerTowerHop
        self.temp['delaybeforeexposure'] = self.display.hwConfig.delayBeforeExposure
        self.temp['delayafterexposure'] = self.display.hwConfig.delayAfterExposure
        self.temp['upanddownwait'] = self.display.hwConfig.upAndDownWait
        self.temp['upanddowneverylayer'] = self.display.hwConfig.upAndDownEveryLayer
        self.temp['upanddownzoffset'] = self.display.hwConfig.upAndDownZoffset
        self.temp['upanddownexpocomp'] = self.display.hwConfig.upAndDownExpoComp

        self.items['value2g1'] = self._strTenth(self.temp['trigger'])
        self.items['value2g2'] = self._strZMove(self.temp['layertowerhop'])
        self.items['value2g3'] = self._strTenth(self.temp['delaybeforeexposure'])
        self.items['value2g4'] = self._strTenth(self.temp['delayafterexposure'])
        self.items['value2g5'] = str(self.temp['upanddownwait'])
        self.items['value2g6'] = str(self.temp['upanddowneverylayer'])
        self.items['value2g7'] = self._strZMove(self.temp['upanddownzoffset'])
        self.items['value2g8'] = self._strTenth(self.temp['upanddownexpocomp'])

        self.temp['blinkexposure'] = self.display.hwConfig.blinkExposure
        self.temp['perpartesexposure'] = self.display.hwConfig.perPartes
        self.temp['tilt'] = self.display.hwConfig.tilt
        self.temp['upanddownuvon'] = self.display.hwConfig.upAndDownUvOn

        self.items['state1g1'] = int(self.temp['blinkexposure'])
        self.items['state1g2'] = int(self.temp['perpartesexposure'])
        self.items['state1g3'] = int(self.temp['tilt'])
        self.items['state1g4'] = int(self.temp['upanddownuvon'])

        super(PageSetupExposure, self).show()
    #enddef


    def _strZMove(self, value):
        return "%.3f" % self.display.hwConfig.calcMM(value)
    #enddef


    def state1g1ButtonRelease(self):
        self._onOff(self.temp, self.changed, 0, 'blinkexposure')
    #enddef


    def state1g2ButtonRelease(self):
        self._onOff(self.temp, self.changed, 1, 'perpartesexposure')
    #enddef


    def state1g3ButtonRelease(self):
        self._onOff(self.temp, self.changed, 2, 'tilt')
    #enddef


    def state1g4ButtonRelease(self):
        self._onOff(self.temp, self.changed, 3, 'upanddownuvon')
    #enddef


    def minus2g1Button(self):
        self._value(self.temp, self.changed, 0, 'trigger', 0, 20, -1, self._strTenth)
    #enddef


    def plus2g1Button(self):
        self._value(self.temp, self.changed, 0, 'trigger', 0, 20, 1, self._strTenth)
    #enddef


    def minus2g2Button(self):
        self._value(self.temp, self.changed, 1, 'layertowerhop', 0, 8000, -20, self._strZMove)
    #enddef


    def plus2g2Button(self):
        self._value(self.temp, self.changed, 1, 'layertowerhop', 0, 8000, 20, self._strZMove)
    #enddef


    def minus2g3Button(self):
        self._value(self.temp, self.changed, 2, 'delaybeforeexposure', 0, 300, -1, self._strTenth)
    #enddef


    def plus2g3Button(self):
        self._value(self.temp, self.changed, 2, 'delaybeforeexposure', 0, 300, 1, self._strTenth)
    #enddef


    def minus2g4Button(self):
        self._value(self.temp, self.changed, 3, 'delayafterexposure', 0, 300, -1, self._strTenth)
    #enddef


    def plus2g4Button(self):
        self._value(self.temp, self.changed, 3, 'delayafterexposure', 0, 300, 1, self._strTenth)
    #enddef


    def minus2g5Button(self):
        self._value(self.temp, self.changed, 4, 'upanddownwait', 0, 600, -1)
    #enddef


    def plus2g5Button(self):
        self._value(self.temp, self.changed, 4, 'upanddownwait', 0, 600, 1)
    #enddef


    def minus2g6Button(self):
        self._value(self.temp, self.changed, 5, 'upanddowneverylayer', 0, 500, -1)
    #enddef


    def plus2g6Button(self):
        self._value(self.temp, self.changed, 5, 'upanddowneverylayer', 0, 500, 1)
    #enddef


    def minus2g7Button(self):
        self._value(self.temp, self.changed, 6, 'upanddownzoffset', -800, 800, -1, self._strZMove)
    #enddef


    def plus2g7Button(self):
        self._value(self.temp, self.changed, 6, 'upanddownzoffset', -800, 800, 1, self._strZMove)
    #enddef


    def minus2g8Button(self):
        self._value(self.temp, self.changed, 7, 'upanddownexpocomp', -10, 300, -1, self._strTenth)
    #enddef


    def plus2g8Button(self):
        self._value(self.temp, self.changed, 7, 'upanddownexpocomp', -10, 300, 1, self._strTenth)
    #enddef

#endclass
