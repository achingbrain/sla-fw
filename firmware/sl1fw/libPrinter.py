# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import os
import logging
from time import time, sleep
import zipfile
import shutil

import defines
import libPages

class Printer(object):

    def __init__(self):

        startTime = time()

        self.logger = logging.getLogger(__name__)
        self.logger.info("SL1 firmware started - version %s", defines.swVersion)

        import libConfig
        self.hwConfig = libConfig.HwConfig(defines.hwConfigFile)
        self.hwConfig.logAllItems()
        self.config = libConfig.PrintConfig(self.hwConfig)

        if self.hwConfig.os.id != "prusa":
            self.logger.error("Wrong hardware! ('%s' is not prusa)" % self.hwConfig.os.id)
            raise Exception(_("Wrong hardware! ('%s' is not prusa)") % self.hwConfig.os.id)
        #endif

        from libHardware import Hardware
        self.hw = Hardware(self.hwConfig, self.config)

        from libInternet import Internet
        self.inet = Internet()

        from libQtDisplay import QtDisplay
        qtdisplay = QtDisplay()

        from libWebDisplay import WebDisplay
        webdisplay = WebDisplay()

        devices = list((qtdisplay, webdisplay))

        from libScreen import Screen
        self.screen = Screen(self.hwConfig)

        from libDisplay import Display
        self.display = Display(self.hwConfig, self.config, devices, self.hw, self.inet, self.screen)

        self.hw.connectMC(self.display.page_systemwait, self.display.actualPage)

        self.inet.startNetMonitor(self.display.assignNetActive)
        self.checkPage = libPages.PageWait(self.display)

        self.hw.powerLed("normal")
        self.hw.uvLed(False)

        self.logger.info("Start time: %f secs", time() - startTime)
    #endclass


    def homeCallback(self, actualPage):
        self.hw.checkTemp(self.checkPage, actualPage, True)
        self.hw.checkFanStatus(self.checkPage, actualPage)
    #enddef


    def m2hm(self, m):
        return "%d:%02d" % divmod(m, 60)
    #enddef


    def dataCleanup(self):
        self.logger.info("removing project files")
        for infile in [ f for f in os.listdir(defines.ramdiskPath) if os.path.isfile(os.path.join(defines.ramdiskPath, f)) ]:
            self.logger.debug("removing '%s'", infile)
            try:
                os.remove(os.path.join(defines.ramdiskPath, infile))
            except Exception as e:
                self.logger.exception("dataCleanup() exception:")
            #endtry
        #endfor
    #enddef


    def checkZipErrors(self):
        message = None
        try:
            zf = zipfile.ZipFile(self.config.zipName, 'r')
            badfile = zf.testzip()
            zf.close()
            if badfile is not None:
                self.logger.error("Corrupted file: %s", badfile)
                message = _("""Your project has corrupted data.

Regenerate it and try again.""")
            #endif
        except Exception as e:
            self.logger.exception("zip read exception:")
            message = _("""Can't read data of your project.

Regenerate it and try again.""")
        #endif

        if message is None:
            return True
        else:
            self.display.page_error.setParams(text = message)
            self.display.doMenu("error")
            return False
        #endif
    #enddef


    def copyZip(self, returnPage):
        if self.config.zipName is None:
            # zdechne to pri kontrole zipu...
            return True
        #endif

        # pokud soubor neni v ramdisku (lan), nakopirujeme ho tam
        (basename, filename) = os.path.split(self.config.zipName)
        if basename == defines.ramdiskPath:
            return True
        #endif

        # test volneho mista
        statvfs = os.statvfs(defines.ramdiskPath)
        ramdiskFree = statvfs.f_frsize * statvfs.f_bavail - 10*1024*1024 # na logfile
        self.logger.debug("Ramdisk free space: %d bytes" % ramdiskFree)
        try:
            filesize = os.path.getsize(self.config.zipName)
            self.logger.debug("Zip file size: %d bytes" % filesize)
        except Exception:
            self.logger.exception("filesize exception:")
            self.display.page_error.setParams(
                    text = _("""Can't read from USB drive.

Check it and try again."""))
            self.display.doMenu("error")
            return False
        #endtry

        try:
            if ramdiskFree < filesize:
                raise Exception("Not enough free space in the ramdisk!")
            #endif
            newZipName = os.path.join(defines.ramdiskPath, filename)
            if os.path.normpath(newZipName) != os.path.normpath(self.config.zipName):
                shutil.copyfile(self.config.zipName, newZipName)
            self.config.zipName = newZipName
        except Exception:
            self.logger.exception("copyfile exception:")
            self.display.page_confirm.setParams(
                    continueFce = self.copyZipRestore,
                    continueParams = { 'returnPage' : returnPage },
                    text = _("""Can't load the file to the printer.

Project'll be printed directly from the USB drive.

DO NOT take it out!"""))
            return self.display.doMenu("confirm")
        #endtry

        return True
    #enddef


    def copyZipRestore(self, **kwargs):
        kwargs['returnPage'].show()
        return "_EXIT_MENU_"
    #enddef


    def updateProgress(self, actualPage):

        if not self.expo.inProgress():
            return "_EXIT_MENU_"
        #endif

        if self.lastLayer == self.expo.actualLayer:
            return
        #endif

        self.lastLayer = self.expo.actualLayer

        # FIXME nepocita s prvnimi delsimi casy!
        # FIXME nepocita s dvojitym osvitem pri per-partes exposure
        time_remain_min = int(round(
            (self.config.totalLayers - self.lastLayer)
            * (self.config.expTime
                + self.timePlus
                + self.hwConfig.delayBeforeExposure
                + self.hwConfig.delayAfterExposure
                + self.config.calibrateRegions * self.config.calibrateTime)
            / 60) + 1)
        timeRemain = self.m2hm(time_remain_min)
        positionMM = self.hwConfig.calcMM(self.expo.position)
        self.logger.debug("TimeRemain: %s", timeRemain)
        time_elapsed_min = int(round((time() - self.printStartTime) / 60))
        timeElapsed = self.m2hm(time_elapsed_min)
        self.logger.debug("TimeElapsed: %s", timeElapsed)
        layer = "Layer: %d/%d" % (self.lastLayer, self.config.totalLayers)
        self.logger.debug(layer)
        height = "Height: %.3f/%.3f mm" % (positionMM, self.totalHeight)
        self.logger.debug(height)
        percent = int(100 * self.lastLayer / self.config.totalLayers)
        self.logger.debug("Percent: %d", percent)

        remain = None
        low_resin = False
        if self.expo.resinVolume:
            remain = self.expo.resinVolume - int(self.expo.resinCount)
            if remain < defines.resinFeedWait:
                self.display.page_feedme.setItems(text = _("Wait for layer finish please."))
                self.expo.doFeedMe()
                return "feedme"
            #endif
            if remain < defines.resinLowWarn:
                self.hw.beepAlarm(1)
                low_resin = True
            #endif
        #endif

        items = {
                'timeremain' : timeRemain,
                'time_remain_sec': time_remain_min * 60,
                'timeelaps' : timeElapsed,
                'time_elapsed_sec': time_elapsed_min * 60,
                'layer' : layer,
                'current_layer': self.lastLayer,
                'total_layers': self.config.totalLayers,
                'layer_height_mm': self.hwConfig.calcMM(self.config.layerMicroSteps),
                'height' : height,
                'position_mm': positionMM,
                'total_mm': self.totalHeight,
                'project_name' : self.config.projectName,
                'percent' : "%d%%" % percent,
                'progress' : percent,
                'resin_used_ml': self.expo.resinCount,
                'resin_remaining_ml': remain,
                'resin_low': low_resin
                }

        if actualPage.pageUI == "print":
            actualPage.showItems(**items)
        else:
            self.display.page_print.setItems(**items)
        #endif

    #enddef


    def jobLog(self, text):
        with open(defines.jobCounter, "a") as jobfile:
            jobfile.write(text)
        #endwith
    #enddef


    def start(self):

        try:
            while True:
                if self.display.hwConfig.showWizard:
                    self.display.hw.beepRepeat(1)
                    self.display.doMenu("wizard")
                    sleep(0.5)    #delay between beep if user selects back from wizard and two beeps at the normal startup
                #endif
                self.display.doMenu("home", self.homeCallback, 30)

                pageWait = libPages.PageWait(self.display, line1 = _("Do not open the cover!"), line2 = _("Checking project data"))
                pageWait.show()

                if not self.copyZip(pageWait):
                    self.dataCleanup()
                    continue
                #endif

                if self.checkZipErrors():
                    pageWait.showItems(line2 = _("Project data OK"))
                else:
                    self.dataCleanup()
                    continue
                #endif

                try:
                    from libExposure import Exposure
                    self.expo = Exposure(self.hwConfig, self.config, self.display, self.hw, self.screen)
                    self.display.initExpoPages(self.expo)
                except Exception:
                    self.logger.exception("exposure exception:")
                    self.display.page_error.setParams(text = _("Can't init exposure display"))
                    self.display.doMenu("error")
                    continue
                #endtry

                # FIXME better format!
                coLog = "job:%s+exp=%.1f/%d+step=%d" % (
                        self.config.projectName,
                        self.config.expTime,
                        int(self.config.expTimeFirst),
                        self.config.layerMicroSteps)
                self.jobLog("\n%s" % (coLog))

                self.hw.checkCoverStatus(self.checkPage, pageWait)  # FIXME status vlakno?

                if self.hw.getFansError():
                    self.display.page_error.setParams(
                            text = _("""Some fans are not spinning!

Check if fans are connected properly and can rotate without resistance."""))
                    self.hw.motorsRelease()
                    self.display.doMenu("error")
                    continue
                #endif

                if self.display.hwConfig.resinSensor:
                    # TODO vyzadovat zavreny kryt po celou dobu!
                    pageWait.showItems(line2 = _("Measuring resin volume"), line3 = _("Do NOT TOUCH the printer"))
                    volume = self.hw.getResinVolume()
                    fail = True

                    if not volume:
                        self.display.page_error.setParams(
                                text = _("""Resin measure failed!

Is tank filled and secured with both screws?"""))
                    elif volume < defines.resinMinVolume:
                        self.display.page_error.setParams(
                                text = _("""Resin volume is too low!

Add resin and try again."""))
                    elif volume > defines.resinMaxVolume:
                        self.display.page_error.setParams(
                                text = _("""Resin volume is too high!

Remove some resin from tank and try again."""))
                    else:
                        fail = False
                    #endif

                    if fail:
                        pageWait.showItems(line1 = _("Problem with resin volume"), line2 = _("Moving platform up"))
                        self.hw.setTowerProfile('moveFast')
                        self.hw.towerToTop()
                        while not self.hw.isTowerOnTop():
                            sleep(0.25)
                            pageWait.showItems(line3 = self.hw.getTowerPosition())
                        #endwhile
                        self.display.doMenu("error")
                        continue
                    #endif

                    pageWait.showItems(line2 = _("Measured resin volume is approx %d %%") % self.hw.calcPercVolume(volume))
                    self.expo.setResinVolume(volume)
                else:
                    pageWait.showItems(line2 = _("Resin volume measurement is turned off"))
                #endif

                break

            #endwhile

            self.hw.checkCoverStatus(self.checkPage, pageWait)  # FIXME status vlakno?

            self.screen.getImgBlack()
            self.hw.uvLed(True)
            self.hw.setUvLedCurrent(self.hwConfig.uvCurrent)

            if self.hwConfig.warmUp > 0:
                for sd in xrange(0, self.hwConfig.warmUp):
                    pageWait.showItems(line3 = _("Warm up: %d minute(s)") % self.hwConfig.warmUp - sd) # TODO ngettext()
                    sleep(60)
                #endfor
            #endif

            if self.hwConfig.tilt:
                pageWait.showItems(line3 = _("Moving tank down"))
                self.hw.tiltDownWait()
            #endif

            pageWait.showItems(line3 = _("Moving platform down"))
            self.hw.setTowerProfile('layer')
            self.hw.towerToPosition(0.05)
            while not self.display.hw.isTowerOnPosition():
                sleep(0.25)
            #endwhile

            if self.hwConfig.tilt:
                pageWait.showItems(line3 = _("Tank calibration 1/3"))
                tiltStartTime = time()
                self.hw.tiltLayerUpWait()
                self.hw.tiltLayerDownWait()
                tiltTime1 = time() - tiltStartTime
                sleep(0.5)

                pageWait.showItems(line3 = _("Tank calibration 2/3"))
                tiltStartTime = time()
                self.hw.tiltLayerUpWait()
                self.hw.tiltLayerDownWait()
                tiltTime2 = time() - tiltStartTime
                sleep(0.5)

                pageWait.showItems(line3 = _("Tank calibration 3/3"))
                tiltStartTime = time()
                self.hw.tiltLayerUpWait()
                self.hw.tiltLayerDownWait()
                tiltTime3 = time() - tiltStartTime
                sleep(0.5)

                self.timePlus = round((tiltTime1 + tiltTime2 + tiltTime3) / 3, 3)
                self.logger.debug("tilt time plus: %.3f (%.3f, %.3f, %.3f)",
                        self.timePlus, tiltTime1, tiltTime2, tiltTime3)
            else:
                self.timePlus = 5 # TODO cca, nutno doladit podle rychlosti sroubu
            #endif

            self.hw.towerMoveAbsoluteWait(0)    # first layer will move up

            self.totalHeight = self.config.totalLayers * self.hwConfig.calcMM(self.config.layerMicroSteps)   # FIXME spatne se spocita pri zlomech (layerMicroSteps 2 a 3)
            self.lastLayer = 0

            if self.hwConfig.blinkExposure:
                self.hw.uvLed(False)
            #endif

            self.printStartTime = time()
            self.logger.debug("printStartTime: " + str(self.printStartTime))

            self.display.setPage("print")
            self.expo.start()
            self.display.doMenu(None, self.updateProgress)

            if self.expo.exception is not None:
                raise Exception("Exposure thread exception: %s" % str(self.expo.exception))
            #endif

            printTime = self.m2hm(int((time() - self.printStartTime) / 60))
            self.logger.info("job finished, real printing time is %s", printTime)
            self.jobLog(" - print time: %s  resin: %.1f ml" % (printTime, self.expo.resinCount) )

            self.display.shutDown(False if self.expo.canceled else self.hwConfig.autoOff)

        except Exception:
            self.logger.exception("run() exception:")
            items = {
                    'text' : _("FIRMWARE FAILURE - Something went wrong!"),
                    }
            ip = self.inet.getIp()
            if ip != "none":
                items['text'] += _("""
Please send the contents of %s/logf to info@prusa3d.com
Thank you""") % ip
                items.update({
                    "qr1"   : "http://%s/logf" % ip,
                    "qr1label" : "Logfile",
                    })
            #endif
            self.hw.powerLed("error")
            self.display.page_exception.setParams(**items)
            self.display.setPage("exception")
            if hasattr(self, 'expo') and self.expo.inProgress():
                self.expo.waitDone()
            #endif
            while True:
                sleep(10)
            #endwhile
        #endtry

    #enddef

#endclass
