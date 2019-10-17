# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from time import time, sleep

from sl1fw import defines
from sl1fw.libConfig import ConfigException
from sl1fw.pages.base import Page
from sl1fw.pages import page
from sl1fw.pages.move import MovePage
from sl1fw.pages.uvcalibration import PageUvCalibration
from sl1fw.pages.wait import PageWait


@page
class PageCalibrationStart(Page):
    Name = "calibrationstart"

    def __init__(self, display):
        super(PageCalibrationStart, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Calibration step 1/11")
    #enddef


    def show(self):
        self.items.update({
            'imageName' : "06_tighten_knob.jpg",
            'text' : _("If the platform is not yet inserted, insert it according to the picture at 0° angle and secure it with the black knob.")})
        super(PageCalibrationStart, self).show()
    #enddef


    def contButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line1 = _("Tank axis homing"))
        pageWait.show()

        self.display.hw.tiltSyncWait(retries = 2) # FIXME MC cant properly home tilt while tower is moving
        self.display.hw.tiltHomeCalibrateWait()
        #tower home check
        pageWait.showItems(line1 = _("Tower axis homing check"))
        for i in range(3):
            if not self.display.hw.towerSyncWait():
                return "towersensitivity"
        #endfor
        self.display.hw.powerLed("normal")
        return "calibration2"
    #enddef


    def backButtonRelease(self):
        return "calibrationconfirm"
    #enddef


    def _OK_(self):
        return "calibration2"
    #enddef

    def _EXIT_(self):
        self.display.hw.motorsRelease()
        return "_EXIT_"
    #enddef

#endclass


@page
class PageCalibration2(Page):
    Name = "calibration2"

    def __init__(self, display):
        super(PageCalibration2, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Calibration step 2/11")
    #enddef


    def show(self):
        self.items.update({
            'imageName' : "01_loosen_screws.jpg",
            'text' : _("Loosen the small screw on the cantilever with an allen key. Be careful not to unscrew it completely.\n\n"
                "Some SL1 printers may have two screws - see the handbook for more information.")})
        super(PageCalibration2, self).show()
    #enddef


    def contButtonRelease(self):
        return "calibration3"
    #endif


    def backButtonRelease(self):
        return "calibrationconfirm"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef

#endclass


@page
class PageCalibration3(Page):
    Name = "calibration3"

    def __init__(self, display):
        super(PageCalibration3, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Calibration step 3/11")
    #enddef


    def show(self):
        self.items.update({
            'imageName' : "02_place_bed.jpg",
            'text' : _("Unscrew the tank, rotate it by 90 degrees and place it flat across the tilt bed. Remove the tank screws completely!")})
        super(PageCalibration3, self).show()
    #enddef


    def contButtonRelease(self):
        pageWait = PageWait(self.display, line1 = _("Setting start position"))
        pageWait.show()

        self.display.hw.powerLed("warn")
        self.display.hw.setTiltProfile('homingFast')
        self.display.hw.tiltMoveAbsolute(self.display.hw._tiltCalibStart)
        while self.display.hw.isTiltMoving():
            sleep(0.25)
        #endwhile
        self.display.hw.powerLed("normal")
        return "calibration4"
    #endif


    def backButtonRelease(self):
        return "calibrationconfirm"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef

#endclass


@page
class PageCalibration4(Page):
    Name = "calibration4"

    def __init__(self, display):
        super(PageCalibration4, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Calibration step 4/11")
    #enddef


    def show(self):
        self.items.update({
            'imageName' : "03_proper_aligment.jpg",
            'text' : _("In the next step, move the tilt up/down until the tilt frame is in direct contact with the resin tank. The tilt frame and tank have to be aligned in a perfect line.")})
        super(PageCalibration4, self).show()
    #enddef


    def contButtonRelease(self):
        return "calibration5"
    #endif


    def backButtonRelease(self):
        return "calibrationconfirm"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef

#endclass


@page
class PageCalibration5(MovePage):
    Name = "calibration5"

    def __init__(self, display):
        super(PageCalibration5, self).__init__(display)
        self.pageUI = "tiltmovecalibration"
        self.pageTitle = N_("Calibration step 5/11")
        self.autorepeat = { "upslow" : (3, 1), "downslow" : (3, 1) }
        self.prevTiltHeight = 0
    #enddef


    def show(self):
        self.display.hw.setTiltProfile('moveSlow')
        self.items["value"] = self.display.hw.getTiltPosition()
        self.moving = False
        super(PageCalibration5, self).show()
    #enddef


    def _up(self, slowMoving):
        self.prevTiltHeight = self.display.hw.getTiltPosition()
        if not self.moving:
            self.display.hw.tiltMoveAbsolute(self.display.hw._tiltEnd)
            self.moving = True
        else:
            if self.display.hw.getTiltPosition() == self.display.hw._tiltEnd:
                self.display.hw.beepAlarm(1)
            #endif
        #endif
        self.showItems(value = self.display.hw.getTiltPosition())
    #enddef


    def _down(self, slowMoving):
        self.prevTiltHeight = self.display.hw.getTiltPosition()
        if not self.moving:
            self.display.hw.tiltMoveAbsolute(self.display.hw._tiltCalibStart)
            self.moving = True
        else:
            if self.display.hw.getTiltPosition() == self.display.hw._tiltCalibStart:
                self.display.hw.beepAlarm(1)
            #endif
        #endif
        self.showItems(value = self.display.hw.getTiltPosition())
    #enddef


    def _stop(self):
        self.display.hw.tiltStop()
        if self.prevTiltHeight < self.display.hw.getTiltPosition():
            self.display.hw.tiltGotoFullstep(goUp = 1)
        elif self.prevTiltHeight > self.display.hw.getTiltPosition():
            self.display.hw.tiltGotoFullstep(goUp = 0)
        #endif

        self.showItems(value = self.display.hw.getTiltPosition())
        self.moving = False
    #enddef


    def okButtonRelease(self):
        position = self.display.hw.getTiltPositionMicroSteps()
        if position is None:
            self.logger.error("Invalid tilt position to save!")
            self.display.hw.beepAlarm(3)
        else:
            self.display.hwConfig.tiltHeight = position
        #endif
        return "calibration6"
    #endif


    def backButtonRelease(self):
        return "calibrationconfirm"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef

#endclass


@page
class PageCalibration6(Page):
    Name = "calibration6"

    def __init__(self, display):
        super(PageCalibration6, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Calibration step 6/11")
    #enddef


    def show(self):
        self.items.update({
            'imageName' : "08_clean.jpg",
            'text' : _("Make sure the platform, tank and tilt are PERFECTLY clean.\n\n"
                "The image is for illustation only.")})
        super(PageCalibration6, self).show()
    #enddef


    def contButtonRelease(self):
        return "calibration7"
    #endif


    def backButtonRelease(self):
        return "calibrationconfirm"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef

#endclass


@page
class PageCalibration7(Page):
    Name = "calibration7"

    def __init__(self, display):
        super(PageCalibration7, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Calibration step 7/11")
    #enddef


    def show(self):
        self.items.update({
            'imageName' : "04_tighten_screws.jpg",
            'text' : _("Return the tank to the original position and secure it with tank screws. Make sure you tighten both screws evenly and with the same amount of force.")})
        super(PageCalibration7, self).show()
    #enddef


    def contButtonRelease(self):
        return "calibration8"
    #endif


    def backButtonRelease(self):
        return "calibrationconfirm"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef


    def _BACK_(self):
        return "_BACK_"
    #enddef

#endclass


@page
class PageCalibration8(Page):
    Name = "calibration8"

    def __init__(self, display):
        super(PageCalibration8, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Calibration step 8/11")
    #enddef


    def show(self):
        self.items.update({
            'imageName' : "06_tighten_knob.jpg",
            'text' : _("Check whether the platform is properly secured with the black knob (hold it in place and tighten the knob if needed).\n\n"
                "Do not rotate the platform. It should be positioned according to the picture.")})
        super(PageCalibration8, self).show()
    #enddef


    def contButtonRelease(self):
        self.display.pages['confirm'].setParams(
            continueFce = self.continuePlatformCalib,
            backFce = self.backButtonRelease,
            pageTitle = N_("Calibration step 9/11"),
            imageName = "12_close_cover.jpg",
            text = _("Please close the orange lid."))
        return "confirm"
    #enddef


    def continuePlatformCalib(self):
        self.ensureCoverIsClosed()

        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display,
            line1 = _("Platform calibration"))
        pageWait.show()
        self.display.hw.setTiltProfile('homingFast')
        self.display.hw.setTiltCurrent(defines.tiltCalibCurrent)
        self.display.hw.setTowerPosition(0)
        self.display.hw.setTowerProfile('homingFast')
        self.display.hw.towerMoveAbsolute(self.display.hw._towerAboveSurface)
        while self.display.hw.isTowerMoving():
            sleep(0.25)
        #endwhile
        self.logger.debug("tower position above: %d", self.display.hw.getTowerPositionMicroSteps())
        if self.display.hw.getTowerPositionMicroSteps() != self.display.hw._towerAboveSurface:
            self.display.hw.beepAlarm(3)
            self.display.hw.towerSyncWait()
            self.display.pages['confirm'].setParams(
                continueFce = self.positionFailed,
                text = _("Tower not at the expected position.\n\n"
                    "Is the platform and tank secured in correct position?\n\n"
                    "Press 'Continue' and read the instructions carefully."))
            return "confirm"
        #endif
        self.display.hw.setTowerProfile('homingSlow')
        self.display.hw.towerToMin()
        while self.display.hw.isTowerMoving():
            sleep(0.25)
        #endwhile
        self.logger.debug("tower position min: %d", self.display.hw.getTowerPositionMicroSteps())
        if self.display.hw.getTowerPositionMicroSteps() <= self.display.hw._towerMin:
            self.display.hw.beepAlarm(3)
            self.display.hw.towerSyncWait()
            self.display.pages['confirm'].setParams(
                continueFce = self.positionFailed,
                text = _("Tower not at the expected position.\n\n"
                    "Is the platform and tank secured in correct position?\n\n"
                    "Press 'Continue' and read the instructions carefully."))
            return "confirm"
        #endif
        self.display.hw.towerMoveAbsolute(self.display.hw.getTowerPositionMicroSteps() + self.display.hw._towerCalibPos * 3)
        while self.display.hw.isTowerMoving():
            sleep(0.25)
        #endwhile
        self.display.hw.towerToMin()
        while self.display.hw.isTowerMoving():
            sleep(0.25)
        #endwhile
        self.display.hw.towerMoveAbsolute(self.display.hw.getTowerPositionMicroSteps() + self.display.hw._towerCalibPos)
        while self.display.hw.isTowerMoving():
            sleep(0.25)
        #endwhile
        self.logger.debug("tower position: %d", self.display.hw.getTowerPositionMicroSteps())
        self.display.hwConfig.towerHeight = -self.display.hw.getTowerPositionMicroSteps()
        self.display.hw.setTowerProfile('homingFast')
        self.display.hw.powerLed("normal")
        return "calibration9"
    #endif


    def positionFailed(self):
        return "_BACK_"
    #enddef


    def backButtonRelease(self):
        return "calibrationconfirm"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef


    def _BACK_(self):
        return "_BACK_"
    #enddef

#endclass


@page
class PageCalibration9(Page):
    Name = "calibration9"

    def __init__(self, display):
        super(PageCalibration9, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Calibration step 10/11")
    #enddef


    def show(self):
        self.items.update({
            'imageName' : "05_align_platform.jpg",
            'text' : _("Adjust the platform so it's aligned with the exposition display.\n\n"
                "Front edges of the platform and exposition display need to be parallel.")})
        super(PageCalibration9, self).show()
    #enddef


    def contButtonRelease(self):
        return "calibration10"
    #endif


    def backButtonRelease(self):
        return "calibrationconfirm"
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef

#endclass


@page
class PageCalibration10(Page):
    Name = "calibration10"

    def __init__(self, display):
        super(PageCalibration10, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Calibration step 11/11")
    #enddef


    def show(self):
        self.items.update({
            'imageName' : "07_tighten_screws.jpg",
            'text' : _("Tighten the small screw on the cantilever with an allen key.\n\n"
                "Some SL1 printers may have two screws - tighten them evenly, little by little. See the handbook for more information.")})
        super(PageCalibration10, self).show()
    #enddef


    def contButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line1 = _("Measuring tilt times"))
        pageWait.show()
        self.display.hw.towerSync()
        while not self.display.hw.isTowerSynced():
            sleep(0.25)
        #endwhile
        self.display.hw.tiltSyncWait(2) # FIXME MC cant properly home tilt while tower is moving
        tiltSlowTime = self.getTiltTime(pageWait, slowMove = True)
        tiltFastTime = self.getTiltTime(pageWait, slowMove = False)
        self.display.hw.setTowerProfile('homingFast')
        self.display.hw.setTiltProfile('homingFast')
        self.display.hw.tiltUpWait()
        writer = self.display.hwConfig.get_writer()
        writer.towerHeight = self.display.hwConfig.towerHeight
        writer.tiltHeight = self.display.hwConfig.tiltHeight
        writer.tiltFastTime = tiltFastTime
        writer.tiltSlowTime = tiltSlowTime
        writer.calibrated = True
        try:
            writer.commit()
        except ConfigException:
            self.logger.exception("Cannot save configuration")
            self.display.pages['error'].setParams(
                text=_("Cannot save configuration"))
            return "error"
        #endtry
        self.display.hw.powerLed("normal")
        return PageCalibrationRecalibrateUV.Name
    #endif


    def backButtonRelease(self):
        return PageCalibrationConfirm.Name
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef


    def getTiltTime(self, pageWait, slowMove):
        tiltTime = 0
        total = self.display.hwConfig.measuringMoves
        for i in range(total):
            pageWait.showItems(line2 = (_("Slow move %(count)d/%(total)d") if slowMove else _("Fast move %(count)d/%(total)d")) % { 'count' : i+1, 'total' : total })
            tiltStartTime = time()
            self.display.hw.tiltLayerUpWait()
            self.display.hw.tiltLayerDownWait(slowMove)
            tiltTime += time() - tiltStartTime
        #endfor
        return round(tiltTime / total, 1)
    #enddef

#endclass


@page
class PageCalibrationRecalibrateUV(Page):
    Name = "calibratiorecalibratenuv"

    def __init__(self, display):
        super(PageCalibrationRecalibrateUV, self).__init__(display)
        self.pageUI = "yesno"
        self.pageTitle = N_("Calibrate UV?")
    #enddef

    def prepare(self):
        if self.display.hwConfig.uvPwm < 1:
            while self.display.hwConfig.uvPwm < 1:
                self.display.doMenu(PageUvCalibration.Name)
            #endwhile

            return PageCalibrationEnd.Name
        #endif
    #enddef


    def show(self):
        self.items.update({ 'text' : _("The UV LED is already calibrated.\n\n"
                    "Would you like to recalibrate?")})
        super(PageCalibrationRecalibrateUV, self).show()
    #enddef


    def yesButtonRelease(self):
        self.display.doMenu(PageUvCalibration.Name)
        return PageCalibrationEnd.Name
    #enddef


    def noButtonRelease(self):
        return PageCalibrationEnd.Name
    #enddef

    def _EXIT_(self):
        return "_EXIT_"
    #enddef

#endclass


@page
class PageCalibrationEnd(Page):
    Name = "calibrationend"

    def __init__(self, display):
        super(PageCalibrationEnd, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Calibration done")
    #enddef


    def prepare(self):
        self.display.hwConfig.calibrated = True
        try:
            self.display.hwConfig.write()
        except ConfigException:
            self.logger.exception("Cannot save configuration")
            self.display.pages['error'].setParams(
                text=_("Cannot save configuration"))
            return "error"
        #endtry
    #enddef


    def show(self):
        self.items.update({
            'text' : _("All done, happy printing!\n\n"
                "Tilt settings for Prusa Slicer:\n\n"
                "Tilt time fast: %(fast).1f s\n"
                "Tilt time slow: %(slow).1f s\n"
                "Area fill: %(area)d %%") % {
                'fast' : self.display.hwConfig.tiltFastTime,
                'slow' : self.display.hwConfig.tiltSlowTime,
                'area' : self.display.hwConfig.limit4fast }})
        super(PageCalibrationEnd, self).show()
    #enddef


    def contButtonRelease(self):
        return "_EXIT_"
    #enddef


    def backButtonRelease(self):
        return "_EXIT_"
    #enddef

#endclass


@page
class PageCalibrationConfirm(Page):
    Name = "calibrationconfirm"

    def __init__(self, display):
        super(PageCalibrationConfirm, self).__init__(display)
        self.pageUI = "yesno"
        self.pageTitle = N_("Cancel calibration?")
        self.checkPowerbutton = False
    #enddef


    def show(self):
        self.items.update({
            'text' : _("Do you really want to cancel calibration?\n\n"
                "Machine will not work without going through it.")})
        super(PageCalibrationConfirm, self).show()
    #enddef


    def yesButtonRelease(self):
        return "_EXIT_"
    #endif


    def noButtonRelease(self):
        return "_NOK_"
    #enddef

#endclass
