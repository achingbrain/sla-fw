# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import logging
import threading, queue
from time import sleep
from gettext import ngettext

from sl1fw import defines
from sl1fw.libPages import PageWait

class ExposureThread(threading.Thread):

    def __init__(self, commands, expo, filename):
        super(ExposureThread, self).__init__()
        self.logger = logging.getLogger(__name__)
        self.commands = commands
        self.expo = expo

        config = expo.config
        self.calibAreas = None
        areaMap = {
                2 : (2,1),
                4 : (2,2),
                6 : (3,2),
                8 : (4,2),
                9 : (3,3),
                }
        if config.calibrateRegions:
            if config.calibrateRegions not in areaMap:
                self.logger.warning("bad value calibrateRegions (%d), calibrate mode disabled", config.calibrateRegions)
            else:
                divide = areaMap[config.calibrateRegions]

                width, height = self.expo.screen.getResolution()

                if width > height:
                    x = 0
                    y = 1
                else:
                    x = 1
                    y = 0
                #endif

                stepW = width // divide[x]
                stepH = height // divide[y]

                self.calibAreas = list()
                lw = 0
                time = config.expTime
                for i in range(divide[x]):
                    lh = 0
                    for j in range(divide[y]):
                        w = (i+1) * stepW
                        h = (j+1) * stepH
                        #self.logger.debug("%d,%d (%d,%d)", lw, lh, stepW, stepH)
                        self.calibAreas.append(((lw, lh), (stepW, stepH), time))
                        time += config.calibrateTime
                        lh = h
                    #endfor
                    lw = w
                #endfor

                self.expo.screen.createCalibrationOverlay(areas = self.calibAreas, filename = filename, penetration = config.calibratePenetration)
            #endif
        #endif
    #enddef


    def doFrame(self, picture, position, exposureTime, overlayName, prevWhitePixels, wasStirring, second):

        self.expo.screen.screenshot(second = second)

        self.expo.hw.setTowerProfile('layer')
        if self.expo.hwConfig.tilt:
            if self.expo.hwConfig.layerTowerHop and prevWhitePixels > self.expo.hwConfig.whitePixelsThd:
                self.expo.hw.towerMoveAbsoluteWait(position + self.expo.hwConfig.layerTowerHop)
                self.expo.hw.setTowerProfile('layerMove')
                self.expo.hw.tiltLayerUpWait()
                self.expo.hw.towerMoveAbsoluteWait(position)
            else:
                self.expo.hw.towerMoveAbsoluteWait(position)
                self.expo.hw.tiltLayerUpWait()
            #endif
        else:
            self.expo.hw.towerMoveAbsoluteWait(position + self.expo.hwConfig.layerTowerHop)
            self.expo.hw.towerMoveAbsoluteWait(position)
        #endif
        self.expo.hw.setTowerCurrent(defines.towerHoldCurrent)

        self.expo.screen.screenshotRename()

        if self.expo.hwConfig.delayBeforeExposure:
            sleep(self.expo.hwConfig.delayBeforeExposure / 10.0)
        #endif

        if wasStirring:
            sleep(self.expo.hwConfig.stirringDelay / 10.0)
        #endif

        if self.calibAreas is not None:
            time = exposureTime + self.calibAreas[-1][2] - self.calibAreas[0][2]
        else:
            time = exposureTime
        #endif
        self.logger.debug("exposure started")
        self.expo.display.actualPage.showItems(exposure = time)
        whitePixels = self.expo.screen.blitImg(second = second)

        if self.expo.hwConfig.blinkExposure:
            if self.calibAreas is not None:
                time = 1000 * (exposureTime + self.calibAreas[-1][2] - self.calibAreas[0][2])
                self.expo.hw.uvLed(True, time)

                for area in self.calibAreas:
                    while time > 1000 * (self.calibAreas[-1][2] - area[2]):
                        sleep(0.005)
                        UVIsOn, time = self.expo.hw.getUvLedState()
                        if not UVIsOn:
                            break
                        #endif
                    #endwhile

                    if not UVIsOn:
                        break
                    #endif

                    self.expo.screen.fillArea(area = (area[0], area[1]))
                    #self.logger.debug("blank area")
                #endfor
            else:
                self.expo.hw.uvLed(True, 1000 * exposureTime)
                UVIsOn = True
                while UVIsOn:
                    sleep(0.1)
                    UVIsOn, time = self.expo.hw.getUvLedState()
                #endwhile
            #endif
        else:
            sleep(exposureTime)
            if self.calibAreas is not None:
                lastArea = self.calibAreas[0]
                for area in self.calibAreas[1:]:
                    self.expo.screen.fillArea(area = (lastArea[0], lastArea[1]))
                    #self.logger.debug("blank area")
                    sleep(area[2] - lastArea[2])
                    lastArea = area
                #endfor
            #endif
        #endif

        self.expo.screen.getImgBlack()
        self.logger.debug("exposure done")

        if picture is not None:
            self.expo.screen.preloadImg(
                    filename = picture,
                    overlayName = overlayName,
                    whitePixelsThd = self.expo.hwConfig.whitePixelsThd)
        #endif

        if self.expo.hwConfig.delayAfterExposure:
            sleep(self.expo.hwConfig.delayAfterExposure / 10.0)
        #endif

        if self.expo.hwConfig.tilt:
            slowMove = whitePixels > self.expo.hwConfig.whitePixelsThd
            if slowMove and self.expo.slowLayers:
                self.expo.slowLayers -= 1
            #endif
            if not self.expo.hw.tiltLayerDownWait(slowMove):
                return (False, whitePixels)
            #endif
        #endif

        return (True, whitePixels)
    #enddef


    def doUpAndDown(self):
        self.expo.hw.powerLed("warn")
        if self.expo.hwConfig.blinkExposure and self.expo.hwConfig.upAndDownUvOn:
            self.expo.hw.uvLed(True)
        #endif
        pageWait = PageWait(self.expo.display, line1 = _("Going to the top position"))
        pageWait.show()
        self.expo.hw.setTowerProfile('homingFast')
        self.expo.hw.towerToTop()
        while not self.expo.hw.isTowerOnTop():
            sleep(0.25)
            pageWait.showItems(line2 = self.expo.hw.getTowerPosition())
        #endwhile
        pageWait.showItems(line2 = "")

        for sec in range(self.expo.hwConfig.upAndDownWait):
            cnt = self.expo.hwConfig.upAndDownWait - sec
            pageWait.showItems(line1 = ngettext("Printing will continue in %d second" % cnt,
                "Printing will continue in %d seconds" % cnt, cnt), line2 = "")
            sleep(1)
            if self.expo.hwConfig.coverCheck and not self.expo.hw.isCoverClosed():
                pageWait.showItems(line1 = _("Paused"),
                    line2 = _("Close the cover to continue"))
                while not self.expo.hw.isCoverClosed():
                    sleep(1)
                #endwhile
            #endif
        #endfor

        if self.expo.hwConfig.tilt:
            pageWait.showItems(line1 = _("Stirring the resin"), line2 = "")
            self.expo.hw.stirResin()
        #endif
        pageWait.showItems(line1 = _("Going back"), line2 = "")
        self.expo.position += self.expo.hwConfig.upAndDownZoffset
        if self.expo.position < 0:
            self.expo.position = 0
        #endif
        self.expo.hw.towerMoveAbsolute(self.expo.position)
        while not self.expo.hw.isTowerOnPosition():
            sleep(0.25)
            pageWait.showItems(line2 = self.expo.hw.getTowerPosition())
        #endwhile
        self.expo.hw.powerLed("normal")
        self.expo.display.forcePage("print")
    #endif


    def doWait(self, beep = False):
        command = None
        breakFree = set(("exit", "back", "continue"))
        while not command:
            if beep:
                self.expo.hw.beepAlarm(3)
            #endif
            sleep(1)

            try:
                command = self.commands.get_nowait()
            except queue.Empty:
                command = None
            except Exception:
                self.logger.exception("getCommand exception")
                command = None
            #endtry

            if command in breakFree:
                break
            #endif
        #endwhile

        return command
    #enddef


    def doStuckRelease(self):
        self.expo.hw.powerLed("error")
        self.expo.hw.towerHoldTiltRelease()
        self.expo.display.pages['confirm'].setParams(
            continueFce = self.expo.doContinue,
            backFce = self.expo.doBack,
            beep = True,
            text = _("""The printer got stuck and needs user assistance.

Release the tank mechanism and press Continue.

If you don't want to continue, press the Back button on top of the screen and the actual job will be canceled."""))
        self.expo.display.forcePage("confirm")
        if self.doWait(True) == "back":
            return False
        #endif

        self.expo.hw.powerLed("warn")
        pageWait = PageWait(self.expo.display, line1 = _("Setting start positions"))
        pageWait.show()

        if not self.expo.hw.tiltSyncWait(retries = 1):
            self.expo.display.pages['error'].setParams(
                    backFce = self.expo.doBack,
                    text = _("""Tilt homing failed!

Check the printer's hardware.

The print job was canceled."""))
            self.expo.display.forcePage("error")
            self.doWait(True)
            return False
        #endif

        pageWait.showItems(line1 = _("Stirring the resin"))
        self.expo.hw.stirResin()
        self.expo.hw.powerLed("normal")
        self.expo.display.forcePage("print")
        return True
    #enddef


    def run(self):
        #self.logger.debug("thread started")
        try:
            config = self.expo.config
            prevWhitePixels = 0
            totalLayers = config.totalLayers
            stuck = False
            wasStirring = True
            exposureCompensation = 0.0

            for i in range(totalLayers):

                try:
                    command = self.commands.get_nowait()
                except queue.Empty:
                    command = None
                except Exception:
                    self.logger.exception("getCommand exception")
                    command = None
                #endtry

                if command == "updown":
                    self.doUpAndDown()
                    wasStirring = True
                    exposureCompensation = self.expo.hwConfig.upAndDownExpoComp / 10.0
                #endif

                if command == "exit":
                    break
                #endif

                if command == "pause":
                    if not self.expo.hwConfig.blinkExposure:
                        self.expo.hw.uvLed(False)
                    #endif

                    if self.doWait(False) == "exit":
                        break
                    #endif

                    if not self.expo.hwConfig.blinkExposure:
                        self.expo.hw.uvLed(True)
                    #endif
                #endif

                if command == "feedme" or command == "feedmeByButton":
                    self.expo.hw.powerLed("warn")
                    if self.expo.hwConfig.tilt:
                        self.expo.hw.tiltLayerUpWait()
                    #endif
                    if command == "feedme":
                        reason = _("Resin level low!")
                        beep = True
                    else:
                        reason = _("Manual resin refill")
                        beep = False
                    #endif
                    self.expo.display.pages['feedme'].showItems(text = _("""%s

Please refill the tank up to the 100 %% mark and press Done.

If you don't want to refill, please press the Back button on top of the screen.""") % reason)
                    self.expo.display.forcePage("feedme")
                    self.doWait(beep)

                    if self.expo.hwConfig.tilt:
                        pageWait = PageWait(self.expo.display, line1 = _("Stirring the resin"))
                        pageWait.show()
                        self.expo.hw.setTiltProfile('homingFast')
                        self.expo.hw.tiltDownWait()
                        self.expo.hw.stirResin()
                    #endif
                    wasStirring = True
                    self.expo.hw.powerLed("normal")
                    self.expo.display.forcePage("print")
                #endif

                if self.expo.hwConfig.upAndDownEveryLayer and self.expo.actualLayer and not self.expo.actualLayer % self.expo.hwConfig.upAndDownEveryLayer:
                    self.doUpAndDown()
                    wasStirring = True
                    exposureCompensation = self.expo.hwConfig.upAndDownExpoComp / 10.0
                #endif

                # first layer - extra height + extra time
                if not i:
                    step = config.layerMicroStepsFirst
                    time = config.expTimeFirst
                # second two layers - normal height + extra time
                elif i < 3:
                    step = config.layerMicroSteps
                    time = config.expTimeFirst
                # next config.fadeLayers is fade between config.expTimeFirst and config.expTime
                elif i < config.fadeLayers + 3:
                    step = config.layerMicroSteps
                    # expTimes may be changed during print
                    timeLoss = (config.expTimeFirst - config.expTime) / float(config.fadeLayers)
                    self.logger.debug("timeLoss: %0.3f", timeLoss)
                    time = config.expTimeFirst - (i - 2) * timeLoss
                # standard parameters to first change
                elif i + 1 < config.slice2:
                    step = config.layerMicroSteps
                    time = config.expTime
                # parameters of second change
                elif i + 1 < config.slice3:
                    step = config.layerMicroSteps2
                    time = config.expTime2
                # parameters of third change
                else:
                    step = config.layerMicroSteps3
                    time = config.expTime3
                #endif

                time += exposureCompensation
                exposureCompensation = 0.0

                self.expo.actualLayer = i + 1
                self.expo.position += step
                self.logger.debug("LAYER %04d/%04d (%s)  steps: %d  position: %d time: %.3f  slowLayers: %d",
                        self.expo.actualLayer, totalLayers, config.toPrint[i], step, self.expo.position, time, self.expo.slowLayers)

                if i < 2:
                    overlayName = 'calibPad'
                elif i < config.calibrateInfoLayers + 2:
                    overlayName = 'calib'
                else:
                    overlayName = None
                #endif

                (success, whitePixels) = self.doFrame(config.toPrint[i+1] if i+1 < totalLayers else None,
                        self.expo.position + self.expo.hwConfig.calibTowerOffset,
                        time,
                        overlayName,
                        prevWhitePixels,
                        wasStirring,
                        False)

                if not success and not self.doStuckRelease():
                    self.expo.hw.powerLed("normal")
                    self.expo.canceled = True
                    stuck = True
                    break
                #endif

                # exposure second part too
                if self.expo.perPartes and whitePixels > self.expo.hwConfig.whitePixelsThd:
                    (success, dummy) = self.doFrame(config.toPrint[i+1] if i+1 < totalLayers else None,
                            self.expo.position + self.expo.hwConfig.calibTowerOffset,
                            time,
                            overlayName,
                            whitePixels,
                            wasStirring,
                            True)

                    if not success and not self.doStuckRelease():
                        stuck = True
                        break
                    #endif
                #endif

                prevWhitePixels = whitePixels
                wasStirring = False

                # /1000 - we want cm3 (=ml) not mm3
                self.expo.resinCount += float(whitePixels * self.expo.pixelSize * self.expo.hwConfig.calcMM(step) / 1000)
                self.logger.debug("resinCount: %f" % self.expo.resinCount)

                if self.expo.hwConfig.trigger:
                    self.expo.hw.cameraLed(True)
                    sleep(self.expo.hwConfig.trigger / 10.0)
                    self.expo.hw.cameraLed(False)
                #endif

            #endfor

            self.expo.hw.saveUvStatistics()
            self.expo.hw.uvLed(False)

            if not stuck:
                pageWait = PageWait(self.expo.display, line1 = _("Moving platform to the top"))
                pageWait.show()

                self.expo.hw.setTowerProfile('homingFast')
                self.expo.hw.towerToTop()
                while not self.expo.hw.isTowerOnTop():
                    sleep(0.25)
                #endwhile
            #endif

            self.expo.display.forcePage("finished")

        except Exception as e:
            self.logger.exception("run() exception:")

            self.expo.display.pages['error'].setParams(
                backFce=lambda: "home",
                text=_(
                    "Print failed due to an unexpected error :-(\n"
                    "\n"
                    "Please follow the instructions in Chapter 3.1 in the handbook to learn how to save a log file. "
                    "Please send the log to us and help us improve the printer.\n"
                    "\n"
                    "Thank you!"
                ))
            self.expo.display.forcePage("error")
        #endtry

        #self.logger.debug("thread ended")
    #enddef

#endclass


class Exposure(object):

    def __init__(self, hwConfig, config, display, hw, screen):
        self.logger = logging.getLogger(__name__)
        self.hwConfig = hwConfig
        self.config = config
        self.display = display
        self.hw = hw
        self.screen = screen
        self.pixelSize = self.hwConfig.pixelSize ** 2
        self.resinCount = 0.0
        self.resinVolume = None
        self.canceled = False
        self.expoThread = None
        self.zipName = None
    #enddef


    def setProject(self, zipName):
        self.zipName = zipName
    #enddef


    def loadProject(self):
        if not self.screen.openZip(filename = self.zipName):
            return False
        #endif
        self.perPartes = self.screen.createMasks(perPartes = self.hwConfig.perPartes)
        self.position = 0
        self.actualLayer = 0
        self.expoCommands = queue.Queue()
        self.screen.initOverlays()
        self.expoThread = ExposureThread(self.expoCommands, self, self.config.toPrint[0])
        self.screen.preloadImg(
                filename = self.config.toPrint[0],
                overlayName = 'calibPad',
                whitePixelsThd = self.hwConfig.whitePixelsThd)
        self.slowLayers = self.config.layersSlow
        return True
    #enddef


    def start(self):
        if self.expoThread:
            self.expoThread.start()
        else:
            self.logger.error("Can't start exposure thread")
        #endif
    #enddef


    def inProgress(self):
        if self.expoThread:
            return self.expoThread.is_alive()
        else:
            return False
        #endif
    #enddef


    def waitDone(self):
        if self.expoThread:
            self.expoThread.join()
        #endif
    #enddef


    def doUpAndDown(self):
        self.expoCommands.put("updown")
    #enddef


    def doExitPrint(self):
        self.expoCommands.put("exit")
    #enddef


    def doFeedMe(self):
        self.expoCommands.put("feedme")
    #enddef


    def doFeedMeByButton(self):
        self.expoCommands.put("feedmeByButton")
    #enddef


    def doPause(self):
        self.expoCommands.put("pause")
    #enddef


    def doContinue(self):
        self.expoCommands.put("continue")
    #enddef


    def doBack(self):
        self.expoCommands.put("back")
    #enddef


    def setResinVolume(self, volume):
        if volume is None:
            self.resinVolume = None
        else:
            self.resinVolume = volume + int(self.resinCount)
        #endif
    #enddef

#endclass

