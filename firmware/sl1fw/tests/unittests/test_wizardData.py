# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import asdict

from sl1fw.tests.base import Sl1fwTestCase
from sl1fw.pages.wizard import WizardData


class TestWizardData(Sl1fwTestCase):

    def test_wizardData(self):
        wd = WizardData()

        wd.osVersion = "1.2.3"
        wd.a64SerialNo = "CZPX2919X009XK00000"
        wd.mcSerialNo = "CZPX2919X012X100000"
        wd.mcFwVersion = "0.11.3"
        wd.mcBoardRev = "6c"
        wd.towerHeight = 96000
        wd.tiltHeight = 4928
        wd.uvPwm = 0

        wd.wizardUvVoltageRow1 = [ 13944, 14975, 16129,]
        wd.wizardUvVoltageRow2 = [ 13996, 15011, 16129,]
        wd.wizardUvVoltageRow3 = [ 13935, 14975, 16068,]
        wd.wizardFanRpm = [ 1861, 3750, 1120,]
        wd.wizardTempUvInit = 34.2
        wd.wizardTempUvWarm = 41.2
        wd.wizardTempAmbient = 25.6
        wd.wizardTempA64 = 54.6
        wd.wizardResinVolume = 130
        wd.towerSensitivity = 0

        self.assertEqual(len(asdict(wd)), 18, "WizardData completeness")
