# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018 Prusa Research s.r.o. - www.prusa3d.com

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
        self.logger.info("Start at " + str(startTime))

        import libConfig
        self.hwConfig = libConfig.HwConfig(defines.hwConfigFile)
        self.config = libConfig.PrintConfig(self.hwConfig)

        if self.hwConfig.os.id != "prusa":
            self.logger.error("Wrong hardware! ('%s' is not prusa)" % self.hwConfig.os.id)
            raise Exception("Wrong hardware! ('%s' is not prusa)" % self.hwConfig.os.id)
        #endif

        from libHardware import Hardware
        self.hw = Hardware(self.hwConfig, self.config)

        from libInternet import Internet
        self.inet = Internet()

        from libQtDisply import QtDisplay
        qtdisplay = QtDisplay()

#        from libWebDisplay import WebDisplay
#        webdisplay = WebDisplay()

#        devices = list((qtdisplay, webdisplay))
        devices = list((qtdisplay, ))

        from libScreen import Screen
        self.screen = Screen(self.hwConfig)

        from libDisplay import Display
        self.display = Display(self.hwConfig, self.config, devices, self.hw, self.inet, self.screen)
        self.inet.startNetMonitor(self.display.assignNetActive)

        self.logger.info("Software version: %s", defines.swVersion)
        self.hwConfig.logAllItems()

        # pokud neni usb storage, nic neprecte a bude vsude default
        self.config.parseFile(os.path.join(defines.usbPath, defines.configFile))
        self.config.logAllItems()

        self.checkPage = libPages.PageWait(self.display)

        self.hw.powerLed("normal")

        self.logger.info("Start time: " + str(time() - startTime))
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
        logfile = os.path.basename(defines.printerlog)
        for infile in [ f for f in os.listdir(defines.ramdiskPath) if os.path.isfile(os.path.join(defines.ramdiskPath, f)) ]:
            if infile != logfile:
                self.logger.debug("removing '%s'", infile)
                try:
                    os.remove(os.path.join(defines.ramdiskPath, infile))
                except Exception as e:
                    self.logger.exception("dataCleanup() exception:")
                #endtry
            #endif
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
                message = "Corrupted datafile."
            #endif
        except Exception as e:
            self.logger.exception("zip read exception:")
            message = "Can't read project data."
        #endif

        if message is None:
            return True
        else:
            self.display.page_error.setParams(
                    line1 = "Your project has a problem:",
                    line2 = message,
                    line3 = "Regenerate it and try again.")
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
                    line1 = "Can't read from USB drive.",
                    line2 = "Check it and try again.")
            self.display.doMenu("error")
            return False
        #endtry

        try:
            if ramdiskFree < filesize:
                raise Exception("Not enough free space in the ramdisk!")
            #endif
            newZipName = os.path.join(defines.ramdiskPath, filename)
            shutil.copyfile(self.config.zipName, newZipName)
            self.config.zipName = newZipName
        except Exception:
            self.logger.exception("copyfile exception:")
            self.display.page_confirm.setParams(
                    continueFce = self.copyZipRestore,
                    continueParmas = { 'returnPage' : returnPage },
                    line1 = "Can't load the file to the printer.",
                    line2 = "Project'll be printed directly from",
                    line3 = "the USB drive. DO NOT take it out!")
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
        self.hw.logTemp()

        # FIXME nepocita s prvnimi delsimi casy!
        timeRemain = self.m2hm(int(round(
            (self.config.totalLayers - self.lastLayer)
            * (self.config.expTime
                + self.timePlus
                + self.config.tiltDelayBefore
                + self.config.tiltDelayAfter
                + self.config.calibrateRegions * self.config.calibrateTime)
            / 60) + 1))
        positionMM = self.hwConfig.calcMM(self.expo.position)
        self.logger.debug("TimeRemain: %s", timeRemain)
        timeElapsed = self.m2hm(int(round((time() - self.printStartTime) / 60)))
        self.logger.debug("TimeElapsed: %s", timeElapsed)
        layer = "Layer: %d/%d" % (self.lastLayer, self.config.totalLayers)
        self.logger.debug(layer)
        height = "Height: %.3f/%.3f mm" % (positionMM, self.totalHeight)
        self.logger.debug(height)
        percent = int(100 * self.lastLayer / self.config.totalLayers)
        self.logger.debug("Percent: %d", percent)
        resinCount = "(%.1f ml)" % self.expo.resinCount

        if actualPage.pageUI == "print":
            actualPage.showItems(
                    timeremain = timeRemain,
                    timeelaps = timeElapsed,
                    line1 = layer,
                    line2 = height,
                    line3 = self.config.projectName,
                    line4 = resinCount,
                    percent = "%d%%" % percent,
                    progress = percent)
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
                if not self.config.direct:
                    self.display.doMenu("home", self.homeCallback, 5)
                #endif

                # akce co nejsou print neresime
                action = self.config.action
                if action != "print":
                    self.logger.warning("unknown action '%s'", action)
                    self.display.page_error.setParams(line1 = "Invalid project file")
                    self.display.doMenu("error")
                    # nepipat na strance home
                    self.display.page_home.firstRun = False
                    continue
                #endif

                pageWait = libPages.PageWait(self.display, line1 = "Do not open the cover!", line2 = "Checking project data")
                pageWait.show()

                if not self.copyZip(pageWait):
                    # nepipat na strance home
                    self.display.page_home.firstRun = False
                    self.dataCleanup()
                    continue
                #endif

                if self.checkZipErrors():
                    pageWait.showItems(line2 = "Project data OK")
                else:
                    # nepipat na strance home
                    self.display.page_home.firstRun = False
                    self.dataCleanup()
                    continue
                #endif

                try:
                    from libExposure import Exposure
                    self.expo = Exposure(self.hwConfig, self.config, self.display, self.hw, self.screen)
                    self.display.initExpoPages(self.expo)
                except Exception:
                    self.logger.exception("exposure exception:")
                    self.display.page_error.setParams(line2 = "Can't init exposure display")
                    self.display.doMenu("error")
                    # nepipat na strance home
                    self.display.page_home.firstRun = False
                    continue
                #endtry

                # FIXME better format!
                coLog = "(%s)job:%s+act=%s+exp=%.1f/%d+step=%d" % (
                        self.config.loadSrc,
                        self.config.projectName,
                        self.config.action,
                        self.config.expTime,
                        int(self.config.expTimeFirst),
                        self.config.layerMicroSteps)
                self.jobLog("\n%s" % (coLog))

                self.hw.checkCoverStatus(self.checkPage, pageWait)  # FIXME status vlakno?
                self.hw.uvLed(True)

                if self.config.startDelay > 0:
                    for sd in xrange(0, self.config.startDelay):
                        pageWait.showItems(line2 = "Start delay %s minute(s)" % self.config.startDelay - sd)
                        sleep(60)
                    #endfor
                #endif

                pageWait.showItems(line2 = "Moving platform to top")
                self.hw.towerSync()
                while not self.display.hw.isTowerSynced():
                    sleep(0.25)
                    pageWait.showItems(line3 = self.display.hw.getTowerPosition())
                #endwhile
                if self.hw.towerSyncFailed():
                    self.hw.uvLed(False)
                    self.hw.motorsRelease()
                    self.display.page_error.setParams(
                            line1 = "Tower homing failed!",
                            line2 = "Check printer's hardware.",
                            line3 = "Job was canceled.")
                    self.display.doMenu("error")
                    # nepipat na strance home
                    self.display.page_home.firstRun = False
                    continue
                #endif

                pageWait.showItems(line2 = "Homing tank", line3 = "")
                if not self.hw.tiltSyncWait(retries = 2):
                    self.hw.uvLed(False)
                    self.hw.motorsRelease()
                    self.display.page_error.setParams(
                            line1 = "Tilt homing failed!",
                            line2 = "Check printer's hardware.",
                            line3 = "Job was canceled.")
                    self.display.doMenu("error")
                    # nepipat na strance home
                    self.display.page_home.firstRun = False
                    continue
                #endif

                self.expo.hw.setTiltProfile('layer')
                self.hw.tiltDownWait()
                self.hw.tiltUpWait()

                break

            #endwhile

            # TODO - kontrola hladiny resinu atd.

            pageWait.showItems(line2 = "Moving tank down")
            self.hw.tiltDownWait()
            pageWait.showItems(line2 = "Moving platform down")
            self.hw.setTowerProfile('layer')
            self.hw.towerToPosition(1)
            while not self.display.hw.isTowerOnPosition():
                sleep(0.25)
                pageWait.showItems(line3 = self.display.hw.getTowerPosition())
            #endwhile

            pageWait.showItems(line3 = "")

            if self.config.tilt:
                pageWait.showItems(line2 = "Tank calibration 1/3")
                tiltStartTime = time()
                self.hw.tiltUpWait()
                self.hw.tiltDownWait()
                tiltTime1 = time() - tiltStartTime
                sleep(1)

                pageWait.showItems(line2 = "Tank calibration 2/3")
                tiltStartTime = time()
                self.hw.tiltUpWait()
                self.hw.tiltDownWait()
                tiltTime2 = time() - tiltStartTime
                sleep(1)

                pageWait.showItems(line2 = "Tank calibration 3/3")
                tiltStartTime = time()
                self.hw.tiltUpWait()
                self.hw.tiltDownWait()
                tiltTime3 = time() - tiltStartTime
                sleep(1)

                self.timePlus = round((tiltTime1 + tiltTime2 + tiltTime3) / 3, 3)
                self.logger.debug("tilt time plus: %.3f (%.3f, %.3f, %.3f)",
                        self.timePlus, tiltTime1, tiltTime2, tiltTime3)
            else:
                self.timePlus = 5 # TODO cca, nutno doladit podle rychlosti sroubu
            #endif

            self.hw.towerMoveAbsoluteWait(0)    # up move for first layer

            self.totalHeight = self.config.totalLayers * self.hwConfig.calcMM(self.config.layerMicroSteps)   # FIXME spatne se spocita pri zlomech (layerMicroSteps 2 a 3)
            self.lastLayer = 0

            self.printStartTime = time()
            self.logger.debug("printStartTime: " + str(self.printStartTime))

            self.display.setPage("print")
            self.config.final = True
            self.expo.start()
            self.display.doMenu(None, self.updateProgress)

            if self.expo.exception is not None:
                raise Exception("Exposure thread exception: %s" % str(self.expo.exception))
            #endif

            printTime = self.m2hm(int((time() - self.printStartTime) / 60))
            self.logger.info("job finished, real printing time is %s", printTime)
            self.jobLog(" - print time: %s  resin: %.1f ml" % (printTime, self.expo.resinCount) )

            self.display.shutDown(self.config.autoOff)

        except Exception:
            self.logger.exception("run() exception:")
            lines = {
                    "line1" : "FIRMWARE FAILURE - Something went wrong!",
                    }
            ip = self.inet.getIp()
            if ip != "none":
                lines.update({
                    "line2" : "Please send the contents of %s/logf" % ip,
                    "line3" : "to info@futur3d.net - Thank you",
                    "qr1"   : "http://%s/logf" % ip,
                    })
            #endif
            self.hw.powerLed("error")
            self.display.page_exception.setParams(**lines)
            self.display.setPage("exception")
            if hasattr(self, 'expo') and self.expo.inProgress():
                self.expo.waitDone()
            #endif
            self.display.shutDown(False)
        #endtry

    #enddef

#endclass
