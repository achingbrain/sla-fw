# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from time import time

from sl1fw import defines
from sl1fw.pages import page
from sl1fw.pages.base import Page
from sl1fw.pages.wait import PageWait


@page
class PagePrint(Page):
    Name = "print"

    def __init__(self, display):
        super(PagePrint, self).__init__(display)
        self.pageUI = "print"
        self.callbackPeriod = 0.1
        self.callbackSkip = 6
        self.totalHeight = None
        self.lastLayer = None
    #enddef


    def prepare(self):
        if self.display.expo.inProgress():
            return
        #endif
        self.display.expo.prepare()
        self.lastLayer = 0

        self.display.expo.start()
        self.display.pages['finished'].data = None
    #enddef


    def callback(self):

        if self.callbackSkip > 5:
            self.callbackSkip = 0
            retc = super(PagePrint, self).callback()
            if retc:
                return retc
            #endif
        #endif

        self.callbackSkip += 1
        expo = self.display.expo

        if self.lastLayer == expo.actualLayer:
            return
        #endif

        self.lastLayer = expo.actualLayer
        config = self.display.expo.config
        calcMM = self.display.hwConfig.calcMM

        time_remain_min = self.display.expo.countRemainTime()
        time_elapsed_min = int(round((time() - self.display.expo.printStartTime) / 60))
        positionMM = calcMM(expo.position)
        percent = int(100 * (self.lastLayer-1) / config.totalLayers)
        self.logger.info("Layer: %04d/%04d  Height [mm]: %.3f/%.3f  Elapsed [min]: %d  Remain [min]: %d  Percent: %d",
                self.lastLayer, config.totalLayers, positionMM,
                self.display.expo.totalHeight, time_elapsed_min, time_remain_min, percent)

        remain = None
        low_resin = False
        if expo.resinVolume:
            remain = expo.resinVolume - int(expo.resinCount)
            if remain < defines.resinFeedWait:
                self.display.pages['feedme'].manual = False
                expo.doFeedMe()
                pageWait = PageWait(self.display, line1 = _("Wait until layer finish"))
                pageWait.show()
            #endif
            if remain < defines.resinLowWarn:
                self.display.hw.beepAlarm(1)
                low_resin = True
            #endif
        #endif

        items = {
            'time_remain_min': time_remain_min,
            'time_elapsed_min': time_elapsed_min,
            'current_layer': self.lastLayer,
            'total_layers': config.totalLayers,
            'layer_height_first_mm': calcMM(config.layerMicroStepsFirst),
            'layer_height_mm': calcMM(config.layerMicroSteps),
            'position_mm': positionMM,
            'total_mm': self.display.expo.totalHeight,
            'project_name': config.projectName,
            'progress': percent,
            'resin_used_ml': expo.resinCount,
            'resin_remaining_ml': remain,
            'resin_low': low_resin
        }

        self.showItems(**items)
        #endif

    #enddef


    def show(self):
        self.items.update({
            'showAdmin' : int(self.display.show_admin), # TODO: Remove once client uses show_admin
            'show_admin': self.display.show_admin,
        })
        super(PagePrint, self).show()
    #enddef


    def feedmeButtonRelease(self):
        self.display.pages['yesno'].setParams(
            yesFce = self.doFeedme,
            text = _("Do you really want to add resin into the tank?"))
        return "yesno"
    #enddef


    def doFeedme(self):
        self.display.pages['feedme'].manual = True
        self.display.expo.doFeedMeByButton()
        self.display.setWaitPage(line1 = _("Wait until layer finish"))
        return "_SELF_"
    #enddef


    def updownButtonRelease(self):
        self.display.pages['yesno'].setParams(
            yesFce = self.doUpAndDown,
            text = _("Do you really want the platform to go up and down?\n\n"
                "It may affect the printed object!"))
        return "yesno"
    #enddef


    def doUpAndDown(self):
        self.display.expo.doUpAndDown()
        self.display.setWaitPage(line1 = _("Up and down will be executed after layer finish"))
        return "_SELF_"
    #enddef


    def settingsButtonRelease(self):
        return "exposure"
    #enddef


    def turnoffButtonRelease(self, hw_button = False):
        if hw_button:
            self.display.pages['yesno'].setParams(
                yesFce = self.exitPrint,
                text = _("Do you really want to cancel the actual job?"))
            return "yesno"
        #endif

        return self.exitPrint()
    #enddef


    def adminButtonRelease(self):
        if self.display.show_admin:
            return "admin"
        #endif
    #enddef

#endclass
