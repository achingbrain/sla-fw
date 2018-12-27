# part of SL1 firmware
# 2018 Prusa Research s.r.o. - www.prusa3d.com
# 2014-2018 Futur3d - www.futur3d.net

import os
import logging
import threading, Queue
import shutil
from time import sleep

import defines

import libPages

class ExposureThread(threading.Thread):

    def __init__(self, commands, expo):
        super(ExposureThread, self).__init__()
        self.logger = logging.getLogger(__name__)
        self.commands = commands
        self.expo = expo
        self.config = self.expo.config
    #enddef


    def doFrame(self, picture, position, exposureTime, overlayName):
        if picture is not None:
            self.expo.screen.preloadImg(filename = picture, overlayName = overlayName)
        #endif
        if self.config.tilt:
            self.expo.hw.towerMoveAbsoluteWait(position)
            self.expo.hw.tiltUpWait()
        else:
            self.towerMoveAbsoluteWait(position + self.config.fakeTiltUp)
            self.towerMoveAbsoluteWait(position)
        #endif
        sleep(self.config.tiltDelayAfter)
        whitePixels = self.expo.screen.blitImg()
        self.logger.debug("exposure started")
        sleep(exposureTime)
        if self.calibAreas is not None:
            for box in self.calibAreas:
                self.expo.screen.fillArea(area = box)
                self.logger.debug("blank area")
                sleep(self.expo.config.calibrateTime)
            #endfor
        #endif
        self.expo.screen.getImgBlack()
        self.logger.debug("exposure done")
        sleep(self.config.tiltDelayBefore)
        if self.config.tilt:
            self.expo.hw.tiltDownWait()
        #endif
        return whitePixels
    #enddef


    def doUpAndDown(self):
        bottomReserve = self.expo.hwConfig.calcMicroSteps(1)

        ms = self.getUpPosition()
        self.expo.hw.powerLed("warn")
        if self.expo.position < bottomReserve:
            self.logger.warn("Wrong platform position for up&down")
            pageWait = libPages.PageWait(self.expo.display,
                    line2 = "Up and down is avaiable only",
                    line3 = "above %d mm of height" % self.expo.hwConfig.calcMM(bottomReserve))
            pageWait.show()
            self.expo.hw.beepAlarm(3)
            sleep(5)
        else:
            mm = self.expo.hwConfig.calcMM(ms)
            self.logger.info("up and down to %d mm", mm)

            pageWait = libPages.PageWait(self.expo.display, line2 = "Going to %d mm" % mm)
            pageWait.show()
            self.expo.hw.towerMoveAbsolute(ms)
            while not self.expo.hw.isTowerOnPosition():
                sleep(0.25)
                pageWait.showItems(line3 = self.expo.hw.getTowerPosition())
            #endwhile
            pageWait.showItems(line3 = "")

            for sec in xrange(self.expo.config.upAndDownWait):
                pageWait.showItems(line2 = "Waiting... (%d)" % (self.expo.config.upAndDownWait - sec))
                sleep(1)
                if self.expo.hwConfig.coverCheck and self.expo.hw.getCoverState():
                    pageWait.showItems(line2 = "Waiting... (cover is open)")
                    while self.expo.hw.getCoverState():
                        sleep(1)
                    #endwhile
                #endif
            #endfor

            ms = self.expo.position - bottomReserve
            pageWait.showItems(line2 = "Going to %d mm" % self.expo.hwConfig.calcMM(ms))
            self.expo.hw.tiltDownWait()
            self.expo.hw.towerMoveAbsolute(ms)
            while not self.expo.hw.isTowerOnPosition():
                sleep(0.25)
                pageWait.showItems(line3 = self.expo.hw.getTowerPosition())
            #endwhile
            sleep(0.5)
            pageWait.showItems(line2 = "Going to %d mm" % self.expo.hwConfig.calcMM(self.expo.position))
            self.expo.hw.towerMoveAbsolute(self.expo.position)
            while not self.expo.hw.isTowerOnPosition():
                sleep(0.25)
                pageWait.showItems(line3 = self.expo.hw.getTowerPosition())
            #endwhile

            pageWait.showItems(line2 = "Tank reset", line3 = "")
            self.expo.hw.tiltUpWait()
            self.expo.hw.tiltDownWait()
            self.expo.hw.tiltUpWait()
        #endif
        self.expo.hw.powerLed("normal")
    #endif


    def getUpPosition(self):
        ms = int(self.expo.position + self.expo.config.finishUp)
        if ms > self.expo.hwConfig.towerHeight:
            ms = self.expo.hwConfig.towerHeight
        #endif
        return ms
    #endif


    def run(self):
        #self.logger.debug("thread started")
        try:
            config = self.expo.config

            self.calibAreas = None

            if config.calibrateRegions:
                if config.calibrateRegions not in self.expo.areaMap:
                    self.logger.warning("bad value calibrateRegions (%d), calibrate mode disabled", config.calibrateRegions)
                else:
                    divide = self.expo.areaMap[config.calibrateRegions]

                    width, height = self.expo.screen.getResolution()

                    if width > height:
                        x = 0
                        y = 1
                    else:
                        x = 1
                        y = 0
                    #endif

                    stepW = width / divide[x]
                    stepH = height / divide[y]

                    self.calibAreas = list()
                    lw = 0
                    for i in xrange(divide[x]):
                        lh = 0
                        for j in xrange(divide[y]):
                            w = (i+1) * stepW
                            h = (j+1) * stepH
                            #self.logger.debug("%d,%d (%d,%d)", lw, lh, stepW, stepH)
                            self.calibAreas.append(((lw,lh),(stepW,stepH)))
                            lh = h
                        #endfor
                        lw = w
                    #endfor

                    self.expo.screen.createCalibrationOverlay(areas = self.calibAreas, baseTime = config.expTime, timeStep = config.calibrateTime)

                    # posledni oblast neni potreba, smaze se cely obraz
                    self.calibAreas.pop()
                #endif
            #endif

            totalLayers = config.totalLayers
            timeLoss = (config.expTimeFirst - config.expTime) / float(config.fadeLayers)
            self.logger.debug("timeLoss: %0.3f", timeLoss)

            for i in xrange(totalLayers):

                try:
                    command = self.commands.get_nowait()
                except Queue.Empty:
                    command = None
                except Exception:
                    self.logger.exception("getCommand exception")
                    command = None
                #endtry

                if command == "updown":
                    self.doUpAndDown()
                    self.expo.display.goBack(2) # preskoc systemwait a printmenu
                #endif

                if command == "exit":
                    break
                #endif

                if config.upAndDownEveryLayer and self.expo.actualLayer and not self.expo.actualLayer % config.upAndDownEveryLayer:
                    self.doUpAndDown()
                    self.expo.display.actualPage.show()
                #endif

                self.expo.hw.checkTemp(self.expo.checkPage, self.expo.display.actualPage)
                self.expo.hw.checkFanStatus(self.expo.checkPage, self.expo.display.actualPage)
                self.expo.hw.checkCoverStatus(self.expo.checkPage, self.expo.display.actualPage)

                # prvni tri vrstvy jsou vzdy s casem config.expTimeFirst
                if i < 3:
                    step = config.layerMicroSteps
                    time = config.expTimeFirst
                    #self.expo.hw.setTiltProfile('firstLayer')
                # dalsich config.fadeLayers je prechod config.expTimeFirst -> config.expTime
                elif i < config.fadeLayers + 3:
                    step = config.layerMicroSteps
                    time = config.expTimeFirst - (i - 2) * timeLoss
                    #self.expo.hw.setTiltProfile('firstLayer')
                # do prvniho zlomu standardni parametry
                elif i + 1 < config.slice2:
                    step = config.layerMicroSteps
                    time = config.expTime
                    #self.expo.hw.setTiltProfile('layer')
                # do druheho zlomu parametry2
                elif i + 1 < config.slice3:
                    step = config.layerMicroSteps2
                    time = config.expTime2
                    #self.expo.hw.setTiltProfile('layer')
                # a pak uz parametry3
                else:
                    step = config.layerMicroSteps3
                    time = config.expTime3
                    #self.expo.hw.setTiltProfile('layer')
                #endif

                self.expo.actualLayer = i + 1
                self.expo.position += step
                self.logger.debug("LAYER %04d/%04d (%s)  step: %d  time: %.3f",
                        self.expo.actualLayer, totalLayers, config.toPrint[i], step, time)

                if i < 2:
                    overlayName = 'calibPad'
                elif i < config.calibrateInfoLayers + 2:
                    overlayName = 'calib'
                else:
                    overlayName = None
                #endif

                whitePixels = self.doFrame(config.toPrint[i+1] if i+1 < totalLayers else None,
                        self.expo.position,
                        time,
                        overlayName)
                # whitePixels can be False
                if whitePixels:
                    # /1000 - we want cm3 (=ml) not mm3
                    self.expo.resinCount += whitePixels * self.expo.pixelSize * self.expo.hwConfig.calcMM(step) / 1000
                #endif
                self.logger.debug("resinCount: %f" % self.expo.resinCount)

            #endfor

            self.expo.hw.uvLed(False)
            self.expo.hw.beepRepeat(3)
            actualPage = self.expo.display.setPage("print")

            actualPage.showItems(
                    timeremain = "0:00",
                    line1 = "Job " + ("is finished" if self.expo.actualLayer == totalLayers else "was canceled"),
                    line2 = "Total height %.3f mm" % self.expo.hwConfig.calcMM(self.expo.position),
                    line3 = "%s" % config.projectName,
                    line4 = "(%.1f ml)" % self.expo.resinCount,
                    percent = "100%",
                    progress = 100)

            ms = self.getUpPosition()
            self.logger.info("go up to %d micro steps", ms)
            self.expo.hw.towerMoveAbsoluteWait(ms)

            actualPage.showItems(line2 = "Please wait", line3 = "Shutting down", line4 = "")

            #self.logger.debug("thread ended")

        except Exception as e:
            self.logger.exception("run() exception:")
            self.expo.exception = e
        #endtry
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
        # FIXME test return value!
        self.screen.openZip(filename = self.config.zipName)
        # here ^^^
        self.screen.createMask()
        self.screen.preloadImg(filename = self.config.toPrint[0], overlayName = 'calibPad')
        self.position = 0
        self.actualLayer = 0
        self.checkPage = libPages.PageWait(display)
        self.expoCommands = Queue.Queue()
        self.expoThread = ExposureThread(self.expoCommands, self)
        self.exception = None
        self.resinCount = 0.0
        self.pixelSize = self.hwConfig.pixelSize ** 2
        self.areaMap = {
                2 : (2,1),
                4 : (2,2),
                6 : (3,2),
                8 : (4,2),
                9 : (3,3),
                }
    #enddef


    def start(self):
        self.expoThread.start()
    #enddef


    def inProgress(self):
        return self.expoThread.isAlive()
    #enddef


    def waitDone(self):
        self.expoThread.join()
    #enddef


    def doUpAndDown(self):
        self.expoCommands.put("updown")
    #enddef


    def doExitPrint(self):
        self.expoCommands.put("exit")
    #enddef

#endclass

