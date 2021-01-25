# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import asdict

import toml
from PIL import Image

from sl1fw.tests.base import Sl1fwTestCase
from sl1fw.libUvLedMeterMulti import UvCalibrationData, UvLedMeterMulti


class TestUvCalibData(Sl1fwTestCase):

    def test_uvCalibData(self):
        ucd = UvCalibrationData()

        # TODO fill
        ucd.uvSensorType = 0
        ucd.uvSensorData = [150, 118, ]
        ucd.uvTemperature = 40.0
        ucd.uvDateTime = "14.10.2019 12:58:32"
        ucd.uvMean = 150.4
        ucd.uvStdDev = 0.0
        ucd.uvMinValue = 118
        ucd.uvMaxValue = 150
        ucd.uvPercDiff = [12.1, -12.1, ]
        ucd.uvFoundPwm = 210

        self.assertEqual(len(asdict(ucd)), 10, "UvCalibrationData completeness")


class TestUvMeterMulti60(Sl1fwTestCase):
    DATA = Sl1fwTestCase.SAMPLES_DIR / "uvcalib_data-60.toml"
    PNG = Sl1fwTestCase.SAMPLES_DIR / "uvcalib-60.png"
    OUT = Sl1fwTestCase.TEMP_DIR / "test.png"

    def setUp(self):
        super().setUp()
        self.uvmeter = UvLedMeterMulti()

    def tearDown(self):
        files = [
            self.OUT,
        ]
        for file in files:
            if file.exists():
                file.unlink()
        super().tearDown()

    def test_generatePNG(self):
        data = toml.load(self.DATA)
        self.uvmeter.save_pic(800, 400, "PWM: %d" % data['uvFoundPwm'], self.OUT, data)
        self.assertSameImage(Image.open(self.OUT), Image.open(self.PNG), 32, "Generated PNG")


# TODO TestUvMeterMulti15
