# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

from sl1fw.tests.integration.base import Sl1FwIntegrationTestCaseBase


class TestIntegrationPages(Sl1FwIntegrationTestCaseBase):
    def test_turnoff(self):
        # Turn off
        self.press("turnoff")
        self.waitPage("yesno")
        self.press("yes")

    def test_control(self):
        self.switchPage("control")
        self.press("top")
        self.waitPage("wait")
        self.waitPage("control", timeout_sec=30)
        self.press("tankres")
        self.waitPage("wait")
        self.waitPage("control", timeout_sec=30)
        self.press("disablesteppers")

        self.test_turnoff()

    def test_support(self):
        self.switchPage("settings")
        self.switchPage("support")

        for page in ["manual", "videos", "sysinfo", "about"]:
            self.switchPage(page)
            self.press("back")
            self.waitPage("support")

        self.press("back")
        self.waitPage("settings")

        self.press("back")
        self.waitPage("home")

        self.test_turnoff()

    def test_advancedsettings(self):
        self.switchPage("settings")
        self.switchPage("advancedsettings")

        # Test moves
        for page in ["towermove", "tiltmove"]:
            self.switchPage(page)

            for action in ["upfast", "upslow", "downfast", "downslow"]:
                self.press(action)

            self.press("back")
            self.waitPage("advancedsettings")

        # Test time settings
        self.switchPage("timesettings")

        self.press("ntpdisable")
        self.press("ntpenable")

        self.switchPage("settime")
        # TODO: Try changing time
        self.press("back")
        self.waitPage("timesettings")

        self.switchPage("settimezone")
        # TODO: Try changing timezone
        self.press("back")
        self.waitPage("timesettings")

        self.switchPage("setdate")
        # TODO: Try changing date
        self.press("back")
        self.waitPage("timesettings")

        self.press("back")
        self.waitPage("advancedsettings")

        # Test language settings
        self.switchPage("setlanguage")
        # TODO: Implement and try changing language
        self.press("back")
        self.waitPage("advancedsettings")

        # Test hostname settings
        self.switchPage("sethostname")
        # Try changning hostname
        self.press("back")
        self.waitPage("advancedsettings")

        # Test login credentials settings
        self.press("setremoteaccess")
        self.waitPage("setlogincredentials")
        self.press("back")
        self.waitPage("advancedsettings")

        # TODO: Test changing settings

        # Test display test - passing
        self.printer.hwConfig.coverCheck = False
        self.press("displaytest")
        self.waitPage("confirm")  # Please unscrew and remove ...
        self.press("cont")
        self.waitPage("confirm")  # Please close the orange lid...
        self.press("cont")
        self.waitPage("yesno")  # Can you see company logo...
        self.press("yes")
        self.waitPage("advancedsettings")

        # Test display test - failing
        self.printer.hwConfig.coverCheck = False
        self.press("displaytest")
        self.waitPage("confirm")  # Please unscrew and remove ...
        self.press("cont")
        self.waitPage("confirm")  # Please close the orange lid...
        self.press("cont")
        self.waitPage("yesno")  # Can you see company logo...
        self.press("no")
        self.waitPage("error")  # No logo, contact service
        self.press("ok")
        self.waitPage("advancedsettings")

        # Test firmware update
        self.press("firmwareupdate")
        self.waitPage("wait")
        self.waitPage("firmwareupdate")
        self.press("back")
        self.waitPage("advancedsettings")

        self.press("back")
        self.waitPage("settings")

        self.press("back")
        self.waitPage("home")

        self.test_turnoff()

    def test_print_not_calibrated(self):
        # Try to print
        self.press("print")
        # Expect problem with not being calibrated
        self.waitPage("yesno")
        # Return to home
        self.press("no")
        self.waitPage("home")

        self.test_turnoff()

    def test_print(self):
        PROJECT_NAME = "numbers"

        # Fake calibration
        self.printer.hwConfig.calibrated = True
        self.printer.hwConfig.fanCheck = False
        self.printer.hwConfig.coverCheck = False
        self.printer.hwConfig.resinSensor = False

        self.press("print")
        self.waitPage("sourceselect")
        choice = None
        for source in self.readItems()['sources']:
            if source['name'] == PROJECT_NAME:
                choice = source['choice']
        self.assertIsNotNone(choice, f"Test project name ({PROJECT_NAME} in sources")
        self.press("source", data={'choice': choice})
        self.waitPage("wait") # reading project data
        self.waitPage("printpreviewswipe")
        self.press("change")
        self.waitPage("change")
        self.press("expossubsecond")
        self.press("back")
        self.waitPage("printpreviewswipe")
        self.press("cont")
        self.waitPage("wait", timeout_sec=30)
        self.waitPage("wait", timeout_sec=30)   # checking project and HW
        self.waitPage("wait", timeout_sec=30)   # resin measure
        self.waitPage("print", timeout_sec=30)  # Actual printing
        self.waitPage("wait", timeout_sec=240)  # Moving platform to the top
        self.waitPage("finished", timeout_sec=30)
        # auto off enabled

    def test_wizard(self):
        self.test_turnoff()

    def test_calibration(self):
        self.printer.hwConfig.coverCheck = False

        self.switchPage("settings")
        self.press("recalibration")
        self.waitPage("yesno")  # Calibrate printer now?
        self.press("yes")
        self.waitPage("confirm")  # If platform is not yet inserted ...
        self.press("cont")
        self.waitPage("wait")  # Printer homing
        self.waitPage("confirm", timeout_sec=30)  # Loosen the small screw ...
        self.press("cont")
        self.waitPage("confirm")  # Unscrew the tank ...
        self.press("cont")
        self.waitPage("wait", timeout_sec=60)  # Moving to start position
        self.waitPage("confirm")  # In the next step, move ...
        self.press("cont")
        self.waitPage("tiltmovecalibration")
        self.press("slowDown")
        self.press("slowUp")
        self.press("ok")
        self.waitPage("confirm")  # Make sure the platform, tank ...
        self.press("cont")
        self.waitPage("confirm")  # Return the tank to the original
        self.press("cont")
        self.waitPage("confirm")  # Check whenever the platform ...
        self.press("cont")
        self.waitPage("confirm")  # Please close the orange lid.
        self.press("cont")
        self.waitPage("wait")  # Platform calibration
        self.waitPage("confirm", timeout_sec=30)  # Adjust the platform ...
        self.press("cont")
        self.waitPage("confirm")  # Tighten the small screw
        self.press("cont")
        self.waitPage("wait")  # Measuring tilt times
        self.waitPage("confirm", timeout_sec=120)  # Calibration done
        self.press("cont")

        self.waitPage("settings")
        self.press("back")
        self.waitPage("home")

        self.test_turnoff()


if __name__ == '__main__':
    unittest.main()
