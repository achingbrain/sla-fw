# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

from time import time

from sl1fw import defines
from sl1fw.libPages import page, Page, PageWait


@page
class PagePrint(Page):
    Name = "print"

    def __init__(self, display):
        super(PagePrint, self).__init__(display)
        self.pageUI = "print"
        self.pageTitle = N_("Print")
        self.callbackPeriod = 0.1
        self.callbackSkip = 6
    #enddef


    def prepare(self):

        if self.display.expo.inProgress():
            return
        #endif

        config = self.display.config

        # FIXME move to MC counters
        coLog = "job:%s+exp=%.1f/%d+step=%d" % (
                config.projectName,
                config.expTime,
                int(config.expTimeFirst),
                config.layerMicroSteps)
        self.jobLog("\n%s" % (coLog))

        self.display.hw.setTowerProfile('layer')
        self.display.hw.towerMoveAbsoluteWait(0)    # first layer will move up

        # FIXME spatne se spocita pri zlomech (layerMicroSteps 2 a 3)
        self.totalHeight = (config.totalLayers-1) * self.display.hwConfig.calcMM(config.layerMicroSteps) + self.display.hwConfig.calcMM(config.layerMicroStepsFirst)
        self.lastLayer = 0

        self.display.screen.getImgBlack()
        self.display.hw.uvLedPwm = self.display.hwConfig.uvPwm
        if not self.display.hwConfig.blinkExposure:
            self.display.hw.uvLed(True)
        #endif

        self.printStartTime = time()
        self.logger.debug("printStartTime: " + str(self.printStartTime))

        self.display.expo.start()
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
        hwConfig = self.display.hwConfig

        if not expo.inProgress():

            if expo.exception is not None:
                raise Exception("Exposure thread exception: %s" % str(expo.exception))
            #endif

            printTime = int((time() - self.printStartTime) / 60)
            self.logger.info("Job finished - real printing time is %s minutes", printTime)
            self.jobLog(" - print time: %s  resin: %.1f ml" % (printTime, expo.resinCount) )

            self.display.hw.stopFans()
            self.display.hw.motorsRelease()
            if hwConfig.autoOff and not expo.canceled:
                self.display.shutDown(True)
            #endif
            return "_EXIT_"
        #endif

        if self.lastLayer == expo.actualLayer:
            return
        #endif

        self.lastLayer = expo.actualLayer
        config = self.display.config

        time_remain_min = self.countRemainTime(expo.actualLayer, expo.slowLayers)
        time_elapsed_min = int(round((time() - self.printStartTime) / 60))
        positionMM = hwConfig.calcMM(expo.position)
        percent = int(100 * (self.lastLayer-1) / config.totalLayers)
        self.logger.info("Layer: %d/%d  Height: %.3f/%.3f mm  Elapsed[min]: %d  Remain[min]: %d  Percent: %d",
                self.lastLayer, config.totalLayers, positionMM,
                self.totalHeight, time_elapsed_min, time_remain_min, percent)

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
                'time_remain_min' : time_remain_min,
                'time_elapsed_min' : time_elapsed_min,
                'current_layer' : self.lastLayer,
                'total_layers' : config.totalLayers,
                'layer_height_first_mm' : self.display.hwConfig.calcMM(config.layerMicroStepsFirst),
                'layer_height_mm' : hwConfig.calcMM(config.layerMicroSteps),
                'position_mm' : positionMM,
                'total_mm' : self.totalHeight,
                'project_name' : config.projectName,
                'progress' : percent,
                'resin_used_ml' : expo.resinCount,
                'resin_remaining_ml' : remain,
                'resin_low' : low_resin
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
            text = _("Do you really want add the resin to the tank?"))
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


    def turnoffButtonRelease(self):
        self.display.pages['yesno'].setParams(
                yesFce = self.exitPrint,
                text = _("Do you really want to cancel the actual job?"))
        return "yesno"
    #enddef


    def adminButtonRelease(self):
        if self.display.show_admin:
            return "admin"
        #endif
    #enddef


    def jobLog(self, text):
        with open(defines.jobCounter, "a") as jobfile:
            jobfile.write(text)
        #endwith
    #enddef

#endclass
