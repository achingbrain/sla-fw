# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from time import monotonic
from time import sleep

from sl1fw import defines
from sl1fw.pages import page
from sl1fw.pages.base import Page
from sl1fw.pages.wait import PageWait
from sl1fw.project.functions import ramdiskCleanup
from sl1fw.project.project import ProjectState

@page
class PagePrintPreviewSwipe(Page):
    Name = "printpreviewswipe"

    # For integration test only
    # TODO: Make MC sim simulate fans spinning
    FanCheckOverride = False

    def __init__(self, display):
        super(PagePrintPreviewSwipe, self).__init__(display)
        self.pageUI = "printpreviewswipe"
    #enddef

    def fillData(self):
        project = self.display.expo.project

        if project.calibrateRegions:
            calibrateRegions = project.calibrateRegions
            calibration = project.calibrateTime
        else:
            calibrateRegions = None
            calibration = None
        #endif

        self.percReq = self.display.hw.calcPercVolume(project.usedMaterial + defines.resinMinVolume)
        if self.percReq <= 100:
            resinVolumeText =  _("Please fill the resin tank to at least %d %% and close the cover.") % self.percReq
        else:
            resinVolumeText =  _("Please fill the resin tank to the 100 % mark and close the cover.\n\n"
                    "Resin will have to be added during this print job.")

        return {
            'name' : project.name,
            'calibrationRegions' : calibrateRegions,
            'date' : project.modificationTime,
            'layers' : project.totalLayers,
            'layer_height_first_mm' : self.display.hwConfig.calcMM(project.layerMicroStepsFirst),
            'layer_height_mm' : self.display.hwConfig.calcMM(project.layerMicroSteps),
            'exposure_time_first_sec' : project.expTimeFirst,
            'exposure_time_sec' : project.expTime,
            'calibrate_time_sec' : calibration,
            'print_time_min' : self.display.expo.countRemainTime(),
            'text' : resinVolumeText
        }
    #enddef

    def show(self):
        self.items.update(self.fillData())
        super(PagePrintPreviewSwipe, self).show()
    #enddef


    def changeButtonRelease(self):
        return "exposure"
    #enddef


    def contButtonRelease(self):
        pageWait = PageWait(self.display, line1 = _("Checking temperatures"))
        pageWait.show()

        temperatures = self.display.hw.getMcTemperatures()
        for i in range(2):
            if temperatures[i] < 0:
                self.display.pages['error'].setParams(
                    text = _("Can't read %s\n\n"
                        "Please check if temperature sensors are connected correctly.") % self.display.hw.getSensorName(i))
                return "error"
            #endif
        #endfor

        if temperatures[1] < defines.minAmbientTemp:
            self.display.pages['yesno'].setParams(
                    pageTitle = N_("Continue?"),
                    yesFce = self.checkProjectAndPrinter,
                    text = _("Ambient temperature is under recommended value.\n\n"
                        "You should heat up the resin and/or increase the exposure times.\n\n"
                        "Do you want to continue?"))
            return "yesno"
        #endif

        if temperatures[1] > defines.maxAmbientTemp:
            self.display.pages['yesno'].setParams(
                    pageTitle = N_("Continue?"),
                    yesFce = self.checkProjectAndPrinter,
                    text = _("Ambient temperature is over recommended value.\n\n"
                        "You should move the printer to a cooler place.\n\n"
                        "Do you want to continue?"))
            return "yesno"
        #endif

        return self.checkProjectAndPrinter()
    #enddef


    def checkProjectAndPrinter(self):
        pageWait = PageWait(self.display,
                line1 = _("Checking project data..."),
                line2 = _("Setting start positions..."),
                line3 = _("Checking fans..."))
        pageWait.show()

        fanStartTime = monotonic()
        self.display.hw.startFans()
        self.display.hw.towerSync()
        self.display.hw.tiltSync()

        # Remove old projects from ramdisk
        ramdiskCleanup(self.logger)
        project_state = self.display.expo.project.copyAndCheck()

        while self.display.hw.isTowerMoving() or self.display.hw.isTiltMoving():
            sleep(0.25)
        #endwhile

        if project_state not in (ProjectState.OK, project_state.PRINT_DIRECTLY):
            if project_state == ProjectState.CANT_READ:
                project_error = _("Can't read project data.\n\nRe-export the project and try again.")
            elif project_state == ProjectState.CORRUPTED:
                project_error = _("Project data is corrupted.\n\nRe-export the project and try again.")
            else:
                project_error = _("Unknown project error.\n\nCheck the project and try again.")
            #endif
            self.display.pages['error'].setParams(text = project_error)
            return "error"
        #endif

        pageWait.showItems(line1 = _("Project data OK"))

        if not self.display.hw.isTowerSynced():
            self.display.pages['error'].setParams(
                    text = _("Tower homing failed!\n\n"
                        "Check the printer's hardware."))
            return "error"
        #endif

        if not self.display.hw.isTiltSynced():
            self.display.pages['error'].setParams(
                    text = _("Tilt homing failed!\n\n"
                        "Check the printer's hardware."))
            return "error"
        #endif

        self.display.hw.setTiltProfile('homingFast')
        self.display.hw.tiltUpWait()
        pageWait.showItems(line2 = _("Start positions OK"))

        fansRunningTime = monotonic() - fanStartTime
        if fansRunningTime < defines.fanStartStopTime:
            sleepTime = defines.fanStartStopTime - fansRunningTime
            self.logger.debug("Waiting %.2f secs for fans", sleepTime)
            sleep(sleepTime)
        #endif

        fansState = self.display.hw.getFansError().values()
        if any(fansState) and not self.FanCheckOverride:
            failedFans = []
            for num, state in enumerate(fansState):
                if state:
                    failedFans.append(self.display.hw.getFanName(num))
                #endif
            #endfor
            self.display.pages['error'].setParams(
                    text = _("Failed: %s\n\n"
                        "Check if fans are connected properly and can rotate without resistance." % ", ".join(failedFans)))
            return "error"
        #endif

        pageWait.showItems(line3 = _("Fans OK"))
        self.display.fanErrorOverride = False
        self.display.checkCoolingExpo = True

        if project_state == project_state.PRINT_DIRECTLY:
            self.display.pages['confirm'].setParams(
                    backFce = self.backButtonRelease,
                    continueFce = self.measureResin,
                    beep = True,
                    text = _("Loading the file into the printer's memory failed.\n\n"
                             "The project will be printed from USB drive.\n\n"
                             "DO NOT remove the USB drive!"))
            return "confirm"
        #endif

        return self.measureResin()
    #enddef


    def measureResin(self):
        self.logger.info(str(self.display.expo.project))

        # start data preparation by libScreen
        self.display.expo.startProjectLoading()

        self.ensureCoverIsClosed()
        self.pageWait = PageWait(self.display, line1 = _("Do not open the orange cover!"))
        self.pageWait.show()

        if self.display.hwConfig.resinSensor:
            self.pageWait.showItems(line2 = _("Measuring resin volume"), line3 = _("Do NOT TOUCH the printer"))
            volume = self.display.hw.getResinVolume()
            fail = True

            if not volume:
                text = _("Resin measuring failed!\n\n"
                        "Is there the correct amount of resin in the tank?\n\n"
                        "Is the tank secured with both screws?")
            elif volume < defines.resinMinVolume:
                text = _("Resin volume is too low!\n\n"
                        "Add enough resin so it reaches at least the %d %% mark and try again.") % self.display.hw.calcPercVolume(defines.resinMinVolume)
            elif volume > defines.resinMaxVolume:
                text = _("Resin volume is too high!\n\n"
                        "Remove some resin from the tank and try again.")
            else:
                fail = False
            #endif

            if fail:
                self.pageWait.showItems(line1 = _("There is a problem with resin volume"), line2 = _("Moving platform up"))
                self.display.hw.setTowerProfile('homingFast')
                self.display.hw.towerToTop()
                while not self.display.hw.isTowerOnTop():
                    sleep(0.25)
                    self.pageWait.showItems(line3 = self.display.hw.getTowerPosition())
                #endwhile
                self.display.pages['error'].setParams(
                        backFce = self.backButtonRelease,
                        text = text)
                return "error"
            #endif

            percMeas = self.display.hw.calcPercVolume(volume)
            self.logger.debug("requested: %d, measured: %d", self.percReq, percMeas)
            self.pageWait.showItems(line2 = _("Measured resin volume is approx. %d %%") % percMeas)
            self.display.expo.setResinVolume(volume)

            if percMeas < self.percReq:
                self.display.pages['confirm'].setParams(
                        backFce = self.backButtonRelease,
                        continueFce = self.refillInfoContinue,
                        beep = True,
                        text = _("Your resin volume is approx %(measured)d %%\n\n"
                            "For your project, %(requested)d %% is needed. A refill may be required during printing.") \
                        % { 'measured' : percMeas, 'requested' : self.percReq})
                return "confirm"
            #endif
        else:
            self.pageWait.showItems(line2 = _("Resin volume measurement is turned off"))
        #endif

        return self.prepareTankAndResin()
    #enddef


    def refillInfoContinue(self):
        self.pageWait.show()
        return self.prepareTankAndResin()
    #enddef


    def prepareTankAndResin(self):
        if self.display.hwConfig.tilt:
            self.pageWait.showItems(line3 = _("Moving tank down"))
            self.display.hw.tiltDownWait()
        #endif

        self.pageWait.showItems(line3 = _("Moving platform down"))
        self.display.hw.setTowerProfile('homingFast')
        self.display.hw.towerToPosition(0.25)
        while not self.display.hw.isTowerOnPosition(retries = 2):
            sleep(0.25)
        #endwhile
        if self.display.hw.towerPositonFailed():
            self.pageWait.showItems(line2 = _("There is a problem with platform position"), line3 = _("Moving platform up"))
            self.display.hw.setTowerProfile('homingFast')
            self.display.hw.towerToTop()
            while not self.display.hw.isTowerOnTop():
                sleep(0.25)
            #endwhile
            self.display.pages['error'].setParams(
                    text = _("The platform has failed to move to the correct position!\n\n"
                    "Clean any cured resin remains or other debris blocking the movement.\n\n"
                    "If everything is clean, the printer needs service. Please contact tech support."))
            return "error"
        #endif

        if self.display.hwConfig.tilt:
            self.pageWait.showItems(line3 = _("Resin stirring"))
            self.display.hw.stirResin()
        #endif


        # collect results from libScreen
        if not self.display.expo.collectProjectData():
            self.display.pages['error'].setParams(
                    text = _("Can't read data of your project.\n\n"
                    "Re-export it and try again."))
            return "error"
        #endif

        return "print"
    #enddef


    def backButtonRelease(self):
        self._BACK_()
        return "_BACK_"
    #enddef


    def _BACK_(self):
        self.allOff()
        ramdiskCleanup(self.logger)
    #enddef


    def _EXIT_(self):
        self._BACK_()
        return "_BACK_"
    #enddef

#endclass
