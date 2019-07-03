# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import os
from time import sleep
import zipfile
import shutil
# Python 2/3 imports
try:
    from time import monotonic
except ImportError:
    # TODO: Remove once we accept Python 3
    from monotonic import monotonic
#endtry

from sl1fw import defines
from sl1fw.libPages import page, Page, PageWait


class PagePrintPreviewBase(Page):

    def __init__(self, display):
        super(PagePrintPreviewBase, self).__init__(display)
    #enddef


    def fillData(self):
        config = self.display.config

        if config.calibrateRegions:
            calibrateRegions = config.calibrateRegions
            calibration = config.calibrateTime
        else:
            calibrateRegions = None
            calibration = None
        #endif

        return {
            'name' : config.projectName,
            'calibrationRegions' : calibrateRegions,
            'date' : config.modificationTime,
            'layers' : config.totalLayers,
            'layer_height_first_mm' : self.display.hwConfig.calcMM(config.layerMicroStepsFirst),
            'layer_height_mm' : self.display.hwConfig.calcMM(config.layerMicroSteps),
            'exposure_time_first_sec' : config.expTimeFirst,
            'exposure_time_sec' : config.expTime,
            'calibrate_time_sec' : calibration,
            'print_time_min' : self.countRemainTime(0, config.layersSlow),
        }
    #enddef

#endclass


@page
class PagePrintPreview(PagePrintPreviewBase):
    Name = "printpreview"

    def __init__(self, display):
        super(PagePrintPreview, self).__init__(display)
        self.pageUI = "printpreview"
        self.pageTitle = N_("Project")
    #enddef


    def show(self):
        self.items.update(self.fillData())
        super(PagePrintPreview, self).show()
    #enddef


    def copyAndCheckZip(self, config):
        confirm = None
        newZipName = None
        if config.zipName:
            # check free space
            statvfs = os.statvfs(defines.ramdiskPath)
            ramdiskFree = statvfs.f_frsize * statvfs.f_bavail - 10*1024*1024 # for other files
            self.logger.debug("Ramdisk free space: %d bytes" % ramdiskFree)
            try:
                filesize = os.path.getsize(config.zipName)
                self.logger.debug("Zip file size: %d bytes" % filesize)
            except Exception:
                self.logger.exception("filesize exception:")
                return (_("Can't read from the USB drive.\n\n"
                    "Check it and try again."), None, None)
            #endtry

            try:
                if ramdiskFree < filesize:
                    raise Exception("Not enough free space in the ramdisk!")
                #endif
                (dummy, filename) = os.path.split(config.zipName)
                newZipName = os.path.join(defines.ramdiskPath, filename)
                if os.path.normpath(newZipName) != os.path.normpath(config.zipName):
                    shutil.copyfile(config.zipName, newZipName)
                #endif
            except Exception:
                self.logger.exception("copyfile exception:")
                confirm = _("Loading the file into the printer's memory failed.\n\n"
                        "The project will be printed from USB drive.\n\n"
                        "DO NOT remove the USB drive!")
                newZipName = config.zipName
            #endtry
        #endif

        try:
            zf = zipfile.ZipFile(newZipName, 'r')
            badfile = zf.testzip()
            zf.close()
            if badfile is not None:
                self.logger.error("Corrupted file: %s", badfile)
                return (_("Corrupted data detected.\n\n"
                    "Re-export the file and try again."), None, None)
            #endif
        except Exception as e:
            self.logger.exception("zip read exception:")
            return (_("Can't read project data.\n\n"
                "Re-export the file and try again."), None, None)
        #endtry

        return (None, confirm, newZipName)
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
                    yesFce = self.contButtonContinue1,
                    text = _("Ambient temperature is under recommended value.\n\n"
                        "You should heat up the resin and/or increase the exposure times.\n\n"
                        "Do you want to continue?"))
            return "yesno"
        #endif

        if temperatures[1] > defines.maxAmbientTemp:
            self.display.pages['yesno'].setParams(
                    pageTitle = N_("Continue?"),
                    yesFce = self.contButtonContinue1,
                    text = _("Ambient temperature is over recommended value.\n\n"
                        "You should move the printer to cooler place.\n\n"
                        "Do you want to continue?"))
            return "yesno"
        #endif

        return self.contButtonContinue1()
    #enddef


    def contButtonContinue1(self):
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
        self.ramdiskCleanup()
        (error, confirm, zipName) = self.copyAndCheckZip(self.display.config)

        while not self.display.hw.isTowerSynced() or not self.display.hw.isTiltSynced():
            sleep(0.25)
        #endwhile

        if error:
            self.display.pages['error'].setParams(text = error)
            return "error"
        #endif

        pageWait.showItems(line1 = _("Project data OK"))

        if self.display.hw.towerSyncFailed():
            self.display.pages['error'].setParams(
                    text = _("Tower homing failed!\n\n"
                        "Check the printer's hardware."))
            return "error"
        #endif

        if self.display.hw.tiltSyncFailed():
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
        if any(fansState):
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
        self.display.expo.setProject(zipName)

        if confirm:
            self.display.pages['confirm'].setParams(
                    backFce = self.backButtonRelease,
                    continueFce = self.contButtonContinue2,
                    beep = True,
                    text = confirm)
            return "confirm"
        #endif

        return self.contButtonContinue2()
    #enddef

    def contButtonContinue2(self):
        self.display.config.logAllItems()
        return "printstart"
    #enddef


    def backButtonRelease(self):
        self._BACK_()
        return "_BACK_"
    #enddef


    def _BACK_(self):
        self.allOff()
        self.ramdiskCleanup()
    #enddef


    def _EXIT_(self):
        self._BACK_()
        return "_BACK_"
    #enddef

#endclass


@page
class PagePrintStart(PagePrintPreviewBase):
    Name = "printstart"

    def __init__(self, display):
        super(PagePrintStart, self).__init__(display)
        self.pageUI = "printstart"
        self.pageTitle = N_("Confirm")
    #enddef


    def show(self):
        self.percReq = self.display.hw.calcPercVolume(self.display.config.usedMaterial + defines.resinMinVolume)
        lines = {
                'name' : self.display.config.projectName,
                }
        if self.percReq <= 100:
            lines.update({
                'text' : _("Please fill the resin tank to at least %d %% and close the cover.") % self.percReq
                })
        else:
            lines.update({
                'text' : _("Please fill the resin tank to the 100 % mark and close the cover.\n\n"
                    "Resin will have to be added during this print job."),
                })
        self.items.update(lines)
        super(PagePrintStart, self).show()
    #enddef


    def changeButtonRelease(self):
        return "exposure"
    #enddef


    def contButtonRelease(self):

        if not self.display.expo.loadProject():
            self.display.pages['error'].setParams(
                    text = _("Can't read data of your project.\n\n"
                        "Regenerate it and try again."))
            return "error"
        #endif

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
                        continueFce = self.contButtonContinue1,
                        beep = True,
                        text = _("Your tank fill is approx %(measured)d %%\n\n"
                            "For your project, %(requested)d %% is needed. A refill may be required during printing.") \
                        % { 'measured' : percMeas, 'requested' : self.percReq})
                return "confirm"
            #endif
        else:
            self.pageWait.showItems(line2 = _("Resin volume measurement is turned off"))
        #endif

        return self.contButtonContinue2()
    #enddef


    def contButtonContinue1(self):
        self.pageWait.show()
        return self.contButtonContinue2()
    #enddef


    def contButtonContinue2(self):
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
                    text = _("The platform has failed to move to the desired position!\n\n"
                        "Please clean any cured resin remains or other pieces that can block the move.\n\n"
                        "If everything is clean, the printer needs service. Please contact tech support."))
            return "error"
        #endif

        if self.display.hwConfig.tilt:
            self.pageWait.showItems(line3 = _("Resin stirring"))
            self.display.hw.stirResin()
        #endif

        return "print"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef

#endclass
