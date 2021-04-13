# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# TODO: Fix following pylint problems
# pylint: disable=inconsistent-return-statements

from time import time, sleep

from sl1fw.errors.errors import TowerBelowSurface
from sl1fw.errors.exceptions import ConfigException, get_exception_code
from sl1fw.functions.checks import tilt_calib_start, tower_calibrate
from sl1fw.pages import page
from sl1fw.pages.base import Page
from sl1fw.pages.move import MovePage
from sl1fw.pages.wait import PageWait
from sl1fw.states.display import DisplayState
from sl1fw.functions.files import save_wizard_history
from sl1fw import defines
from sl1fw.hardware.tilt import TiltProfile


@page
class PageCalibrationBase(Page):

    def backButtonRelease(self):
        return PageCalibrationConfirm.Name
    #enddef


    @staticmethod
    def _BACK_():
        return "_BACK_"
    #enddef


    def _EXIT_(self):
        self.display.state = DisplayState.IDLE
        self.display.hw.motorsRelease()
        return "_EXIT_"
    #enddef

#enddef


@page
class PageCalibrationStart(PageCalibrationBase):
    Name = "calibrationstart"

    def __init__(self, display):
        super(PageCalibrationStart, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Printer calibration")
    #enddef


    def show(self):
        self.items.update({
            'text' : _("Printer is not calibrated!\n\n"
                "Calibrate now?")})
        super(PageCalibrationStart, self).show()
    #enddef


    @staticmethod
    def contButtonRelease():
        return "calibration1"
    #enddef


    @staticmethod
    def _OK_():
        return "calibration1"
    #enddef

#endclass


@page
class PageCalibration1(PageCalibrationBase):
    Name = "calibration1"

    def __init__(self, display):
        super(PageCalibration1, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Calibration step 1/11")
    #enddef


    def show(self):
        self.display.state = DisplayState.CALIBRATION
        self.items.update({
            'imageName' : "calibration-tighten_knob.jpg",
            'text' : _("If the platform is not yet inserted, insert it according to the picture at 0° angle and secure it with the black knob.")})
        super(PageCalibration1, self).show()
    #enddef


    def contButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line1 = _("Tank axis homing"))
        pageWait.show()

        self.display.hw.tilt.sync_wait(retries = 2) # FIXME MC cant properly home tilt while tower is moving
        self.display.hw.tilt.home_calibrate_wait()
        #tower home check
        pageWait.showItems(line1 = _("Tower axis homing check"))
        for __ in range(3):
            if not self.display.hw.towerSyncWait():
                return "towersensitivity"
        #endfor
        self.display.hw.powerLed("normal")
        return "calibration2"
    #enddef


    @staticmethod
    def _OK_():
        return "calibration2"
    #enddef

#endclass


@page
class PageCalibration2(PageCalibrationBase):
    Name = "calibration2"

    def __init__(self, display):
        super(PageCalibration2, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Calibration step 2/11")
    #enddef


    def show(self):
        self.items.update({
            'imageName' : "calibration-loosen_cantilever.jpg",
            'text' : _("Loosen the small screw on the cantilever with an allen key. Be careful not to unscrew it completely.\n\n"
                "Some SL1 printers may have two screws - see the handbook for more information.")})
        super(PageCalibration2, self).show()
    #enddef


    @staticmethod
    def contButtonRelease():
        return "calibration3"
    #endif

#endclass


@page
class PageCalibration3(PageCalibrationBase):
    Name = "calibration3"

    def __init__(self, display):
        super(PageCalibration3, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Calibration step 3/11")
    #enddef


    def show(self):
        self.items.update({
            'imageName' : "calibration-place_bed.jpg",
            'text' : _("Unscrew the tank, rotate it by 90 degrees and place it flat across the tilt bed. Remove the tank screws completely!")})
        super(PageCalibration3, self).show()
    #enddef


    def contButtonRelease(self):
        pageWait = PageWait(self.display, line1 = _("Setting start position"))
        pageWait.show()

        self.display.hw.powerLed("warn")
        tilt_calib_start(self.display.hw)
        self.display.hw.powerLed("normal")
        return "calibration4"
    #endif

#endclass


@page
class PageCalibration4(PageCalibrationBase):
    Name = "calibration4"

    def __init__(self, display):
        super(PageCalibration4, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Calibration step 4/11")
    #enddef


    def show(self):
        self.items.update({
            'imageName' : "calibration-proper_aligment.jpg",
            'text' : _("In the next step, move the tilt up/down until the tilt frame is in direct contact with the resin tank. The tilt frame and tank have to be aligned in a perfect line.")})
        super(PageCalibration4, self).show()
    #enddef


    @staticmethod
    def contButtonRelease():
        return "calibration5"
    #endif

#endclass


@page
class PageCalibration5(MovePage):
    Name = "calibration5"

    def __init__(self, display):
        super(PageCalibration5, self).__init__(display)
        self.pageUI = "tiltmovecalibration"
        self.pageTitle = N_("Calibration step 5/11")
        self.autorepeat = { "upslow" : (2, 1), "downslow" : (2, 1) }
        self.prevTiltHeight = 0
        self.moving = False
    #enddef


    def show(self):
        self.display.hw.tilt.profile_id = TiltProfile.moveSlow
        self.items["value"] = self.display.hw.tilt.position
        self.moving = False
        super(PageCalibration5, self).show()
    #enddef


    def _up(self, slowMoving):
        self.prevTiltHeight = self.display.hw.tilt.position
        if not self.moving:
            self.display.hw.tilt.move_absolute(self.display.hw.tilt.max)
            self.moving = True
        else:
            self.showItems(value = self.display.hw.tilt.position)
            if self.display.hw.tilt.position == self.display.hw.tilt.max:
                self.display.hw.beepAlarm(1)
            #endif
        #endif
    #enddef


    def _down(self, slowMoving):
        self.prevTiltHeight = self.display.hw.tilt.position
        if not self.moving:
            self.display.hw.tilt.move_absolute(defines.tiltCalibrationStart)
            self.moving = True
        else:
            self.showItems(value = self.display.hw.tilt.position)
            if self.display.hw.tilt.position == defines.tiltCalibrationStart:
                self.display.hw.beepAlarm(1)
            #endif
        #endif
    #enddef


    def _stop(self):
        self.display.hw.tilt.stop()
        if self.prevTiltHeight < self.display.hw.tilt.position:
            self.display.hw.tilt.go_to_fullstep(goUp = 1)
        elif self.prevTiltHeight > self.display.hw.tilt.position:
            self.display.hw.tilt.go_to_fullstep(goUp = 0)
        #endif

        self.showItems(value = self.display.hw.tilt.position)
        self.moving = False
    #enddef


    def okButtonRelease(self):
        position = self.display.hw.tilt.position
        if position is None:
            self.logger.error("Invalid tilt position to save!")
            self.display.hw.beepAlarm(3)
        else:
            self.display.hw.config.tiltHeight = position
        #endif
        return "calibration6"
    #endif


    def backButtonRelease(self):
        return PageCalibrationConfirm.Name
    #enddef


    @staticmethod
    def _EXIT_():
        return "_EXIT_"
    #enddef

#endclass


@page
class PageCalibration6(PageCalibrationBase):
    Name = "calibration6"

    def __init__(self, display):
        super(PageCalibration6, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Calibration step 6/11")
    #enddef


    def show(self):
        self.items.update({
            'imageName' : "calibration-clean.jpg",
            'text' : _("Make sure the platform, tank and tilt are PERFECTLY clean.\n\n"
                "The image is for illustration only.")})
        super(PageCalibration6, self).show()
    #enddef


    @staticmethod
    def contButtonRelease():
        return "calibration7"
    #endif

#endclass


@page
class PageCalibration7(PageCalibrationBase):
    Name = "calibration7"

    def __init__(self, display):
        super(PageCalibration7, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Calibration step 7/11")
    #enddef


    def show(self):
        self.items.update({
            'imageName' : "tighten_screws.jpg",
            'text' : _("Return the tank to the original position and secure it with tank screws. Make sure you tighten both screws evenly and with the same amount of force.")})
        super(PageCalibration7, self).show()
    #enddef


    @staticmethod
    def contButtonRelease():
        return "calibration8"
    #endif

#endclass


@page
class PageCalibration8(PageCalibrationBase):
    Name = "calibration8"

    def __init__(self, display):
        super(PageCalibration8, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Calibration step 8/11")
    #enddef


    def show(self):
        self.items.update({
            'imageName' : "calibration-tighten_knob.jpg",
            'text' : _("Check whether the platform is properly secured with the black knob (hold it in place and tighten the knob if needed).\n\n"
                "Do not rotate the platform. It should be positioned according to the picture.")})
        super(PageCalibration8, self).show()
    #enddef


    def contButtonRelease(self):
        self.display.pages['confirm'].setParams(
            continueFce = self.continuePlatformCalib,
            backFce = self.backButtonRelease,
            pageTitle = N_("Calibration step 9/11"),
            imageName = "close_cover.jpg",
            text = _("Please close the orange lid."))
        return "confirm"
    #enddef


    def continuePlatformCalib(self):
        self.ensureCoverIsClosed()
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line1=_("Platform calibration"))
        pageWait.show()
        try:
            tower_calibrate(self.display.hw, self.logger)
        except TowerBelowSurface:
            self.display.pages['confirm'].setParams(
                continueFce=self.positionFailed,
                text=_("Tower not at the expected position.\n\n"
                       "Is the platform and tank secured in correct position?\n\n"
                       "Press 'Continue' and read the instructions carefully."))
            return "confirm"
        self.display.hw.powerLed("normal")
        return "calibration9"
    #endif


    @staticmethod
    def positionFailed():
        return "_BACK_"
    #enddef

#endclass


@page
class PageCalibration9(PageCalibrationBase):
    Name = "calibration9"

    def __init__(self, display):
        super(PageCalibration9, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Calibration step 10/11")
    #enddef


    def show(self):
        self.items.update({
            'imageName' : "calibration-align_platform.jpg",
            'text' : _("Adjust the platform so it's aligned with the exposition display.\n\n"
                "Front edges of the platform and exposition display need to be parallel.")})
        super(PageCalibration9, self).show()
    #enddef


    @staticmethod
    def contButtonRelease():
        return "calibration10"
    #endif

#endclass


@page
class PageCalibration10(PageCalibrationBase):
    Name = "calibration10"

    def __init__(self, display):
        super(PageCalibration10, self).__init__(display)
        self.pageUI = "confirm"
        self.pageTitle = N_("Calibration step 11/11")
    #enddef


    def show(self):
        self.items.update({
            'imageName' : "calibration-tighten_cantilever.jpg",
            'text' : _("Tighten the small screw on the cantilever with an allen key.\n\n"
                "Some SL1 printers may have two screws - tighten them evenly, little by little. See the handbook for more information.")})
        super(PageCalibration10, self).show()
    #enddef


    def contButtonRelease(self):
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line1 = _("Measuring tilt times"))
        self.logger.info("Measuring tilt times")
        pageWait.show()
        self.logger.debug("Setting tower to initial position")
        self.display.hw.towerSync()
        while not self.display.hw.isTowerSynced():
            sleep(0.25)
        #endwhile
        self.logger.debug("Setting tilt to initial position")
        self.display.hw.tilt.sync_wait(2) # FIXME MC cant properly home tilt while tower is moving
        self.logger.info("Measuring slow tilt times")
        tiltSlowTime = self.getTiltTime(pageWait, slowMove = True)
        self.logger.info("Measuring fast tilt times")
        tiltFastTime = self.getTiltTime(pageWait, slowMove = False)
        self.logger.debug("Resetting tower profile")
        self.display.hw.setTowerProfile('homingFast')
        self.logger.debug("Resetting tilt profile")
        self.display.hw.tilt.profile_id = TiltProfile.homingFast
        self.logger.debug("Resetting tilt")
        self.display.hw.tilt.move_up_wait()
        self.logger.debug("Setting calibration data")
        writer = self.display.hw.config.get_writer()
        writer.towerHeight = self.display.hw.config.towerHeight  # TODO: This seems to just copy default to value
        writer.tiltHeight = self.display.hw.config.tiltHeight  # TODO: This seems to just copy default to value
        writer.tiltFastTime = tiltFastTime
        writer.tiltSlowTime = tiltSlowTime
        writer.calibrated = True
        try:
            self.logger.debug("Saving calibration data")
            writer.commit()
            save_wizard_history(defines.hwConfigPath)
        except ConfigException as exception:
            self.logger.exception("Cannot save configuration")
            self.display.pages['error'].setParams(code=get_exception_code(exception).raw_code)
            return "error"
        #endtry
        self.display.hw.powerLed("normal")
        return PageCalibrationEnd.Name
    #endif


    def getTiltTime(self, pageWait, slowMove):
        tiltTime = 0
        total = self.display.hw.config.measuringMoves
        for i in range(total):
            pageWait.showItems(line2 = (_("Slow move %(count)d/%(total)d") if slowMove else _("Fast move %(count)d/%(total)d")) % { 'count' : i+1, 'total' : total })
            self.logger.debug("Measuring tilt time - start")
            tiltStartTime = time()
            self.display.hw.tilt.layer_up_wait()
            self.display.hw.tilt.layer_down_wait(slowMove)
            tiltTime += time() - tiltStartTime
            self.logger.debug("Measuring tilt time - end")
        #endfor
        return round(tiltTime / total, 1)
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
        self.logger.debug("Setting calibrated to True")
        self.display.hw.config.calibrated = True
        try:
            self.logger.debug("Setting configuration")
            self.display.hw.config.write()
        except ConfigException as exception:
            self.logger.exception("Cannot save configuration")
            self.display.pages['error'].setParams(code=get_exception_code(exception).raw_code)
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
                'fast' : self.display.hw.config.tiltFastTime,
                'slow' : self.display.hw.config.tiltSlowTime,
                'area' : self.display.hw.config.limit4fast },
            'no_back' : True })
        super(PageCalibrationEnd, self).show()
    #enddef


    def contButtonRelease(self):
        self.display.state = DisplayState.IDLE
        self.display.hw.motorsRelease()
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
            'text' : _("Do you really want to cancel the calibration?\n\n"
                "The machine will not work without going through it.")})
        super(PageCalibrationConfirm, self).show()
    #enddef


    def yesButtonRelease(self):
        self.display.state = DisplayState.IDLE
        self.display.hw.motorsRelease()
        return "_EXIT_"
    #endif


    @staticmethod
    def noButtonRelease():
        return "_NOK_"
    #enddef

#endclass
