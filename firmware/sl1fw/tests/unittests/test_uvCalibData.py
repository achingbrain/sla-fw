# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import asdict
import toml

from sl1fw.tests.base import Sl1fwTestCase
from sl1fw.pages.uvcalibration import UvCalibrationData
from sl1fw.libUvLedMeterMulti import UvLedMeterMulti
from sl1fw.libUvLedMeterSingle import UvLedMeterSingle


class TestUvCalibData(Sl1fwTestCase):

    def test_uvCalibData(self):
        ucd = UvCalibrationData()

        # TODO fill
        ucd.uvSensorType = 1
        ucd.uvSensorData = [150, 118,]
        ucd.uvTemperature = 40.0
        ucd.uvDateTime = "14.10.2019 12:58:32"
        ucd.uvMean = 150.4
        ucd.uvStdDev = 0.0
        ucd.uvMinValue = 118
        ucd.uvMaxValue = 150
        ucd.uvPercDiff = [12.1, -12.1,]
        ucd.uvFoundPwm = 210

        self.assertEqual(len(asdict(ucd)), 10, "UvCalibrationData completeness")

class TestUvMeterSingle(Sl1fwTestCase):
    DATA = Sl1fwTestCase.SAMPLES_DIR / "uvcalib_data-single.toml"
    PNG = Sl1fwTestCase.SAMPLES_DIR / "uvcalib-single.png"
    OUT = Sl1fwTestCase.TEMP_DIR / "test.png"

    def setUp(self):
        self.uvmeter = UvLedMeterSingle()

    def tearDown(self):
        files = [
            self.OUT,
        ]
        for file in files:
            if file.exists():
                file.unlink()

    def test_generatePNG(self):
        data = toml.load(self.DATA)
        self.uvmeter.savePic(800, 400, "PWM: %d" % data['uvFoundPwm'], self.OUT, data)
        self.assertTrue(self.compareImages(self.OUT, self.PNG), "Generated PNG")

class TestUvMeterMulti(Sl1fwTestCase):
    DATA = Sl1fwTestCase.SAMPLES_DIR / "uvcalib_data-multi.toml"
    PNG = Sl1fwTestCase.SAMPLES_DIR / "uvcalib-multi.png"
    OUT = Sl1fwTestCase.TEMP_DIR / "test.png"

    def setUp(self):
        self.uvmeter = UvLedMeterMulti()

    def tearDown(self):
        files = [
            self.OUT,
        ]
        for file in files:
            if file.exists():
                file.unlink()

    def test_generatePNG(self):
        data = toml.load(self.DATA)
        self.uvmeter.savePic(800, 400, "PWM: %d" % data['uvFoundPwm'], self.OUT, data)
        self.assertTrue(self.compareImages(self.OUT, self.PNG), "Generated PNG")
