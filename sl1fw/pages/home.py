# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.errors.errors import NotUVCalibrated, NotMechanicallyCalibrated
from sl1fw.project.functions import check_ready_to_print
from sl1fw.states.display import DisplayState
from sl1fw.pages import page
from sl1fw.pages.base import Page
from sl1fw.pages.calibration import PageCalibrationStart
from sl1fw.pages.uvcalibration import PageUvCalibrationStart


@page
class PageHome(Page):
    Name = "home"

    def __init__(self, display):
        super(PageHome, self).__init__(display)
        self.pageUI = "home"
        # meni se i z PageFinished!
        self.readyBeep = True

    def show(self):
        super(PageHome, self).show()

        # This is admin leave detection
        self.display.state = DisplayState.IDLE

        if self.readyBeep:
            self.display.hw.beepRepeat(2)
            self.readyBeep = False

    @staticmethod
    def controlButtonRelease():
        return "control"

    @staticmethod
    def settingsButtonRelease():
        return "settings"

    def printButtonRelease(self):
        # FIXME temporary disabled until it works perfectly on all printers
        #       if self.display.hwConfig.showWizard:
        #           return PageWizardInit.Name

        try:
            check_ready_to_print(self.display.hwConfig, self.display.screen.printer_model.calibration(self.display.hw.is500khz))
        except NotUVCalibrated:
            return PageUvCalibrationStart.Name
        except NotMechanicallyCalibrated:
            return PageCalibrationStart.Name

        if not self.display.doMenu("sourceselect"):
            return "_EXIT_"

        return "printpreviewswipe"
