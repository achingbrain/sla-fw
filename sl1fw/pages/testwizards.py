# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.functions.wizards import (
    displaytest_wizard,
    unboxing_wizard,
    kit_unboxing_wizard,
    the_wizard,
    calibration_wizard,
)
from sl1fw.pages import page
from sl1fw.pages.base import Page


@page
class PageTestWizards(Page):
    Name = "testwizards"

    def __init__(self, display):
        super(PageTestWizards, self).__init__(display)
        self.pageUI = "admin"
        self.pageTitle = "Wizards"

    def show(self):
        self.items.update(
            {
                "button1": "Unpacking (C)",
                "button2": "Unpacking (K)",
                "button3": "Selftest",
                "button4": "Calibration",
                "button6": "API Displaytest",
                "button7": "API Unpacking (C)",
                "button8": "API Unpacking (K)",
                "button9": "API Wizard",
                "button10": "API Calibration",
            }
        )
        super(PageTestWizards, self).show()

    def button1ButtonRelease(self):
        self.display.action_manager.start_unboxing(self.display.hw, self.display.hwConfig, kit=False)
        self.display.doMenu("unboxing")
        self.display.action_manager.cleanup_unboxing()
        return "_SELF_"

    def button2ButtonRelease(self):
        self.display.action_manager.start_unboxing(self.display.hw, self.display.hwConfig, kit=True)
        self.display.doMenu("unboxing")
        self.display.action_manager.cleanup_unboxing()
        return "_SELF_"

    def button3ButtonRelease(self):
        self.display.doMenu("wizardinit")
        return "_SELF_"

    def button4ButtonRelease(self):
        self.display.doMenu("calibrationstart")
        return "_SELF_"

    def button6ButtonRelease(self):
        displaytest_wizard(
            self.display.action_manager,
            self.display.hw,
            self.display.hwConfig,
            self.display.screen,
            self.display.runtime_config,
        )

    def button7ButtonRelease(self):
        unboxing_wizard(self.display.action_manager, self.display.hw, self.display.hwConfig)

    def button8ButtonRelease(self):
        kit_unboxing_wizard(self.display.action_manager, self.display.hw, self.display.hwConfig)

    def button9ButtonRelease(self):
        the_wizard(
            self.display.action_manager,
            self.display.hw,
            self.display.hwConfig,
            self.display.screen,
            self.display.runtime_config,
        )

    def button10ButtonRelease(self):
        calibration_wizard(self.display.action_manager, self.display.hw, self.display.hwConfig)
