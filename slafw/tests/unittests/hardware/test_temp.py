# This file is part of the SLA firmware
# Copyright (C) 2022 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import Mock

from slafw.configs.hw import HwConfig
from slafw.errors.errors import UvTempSensorFailed, TempSensorFailed
from slafw.hardware.sl1.temp_sensor import SL1TempSensorUV, SL1STempSensorUV, SL1TempSensorAmbient
from slafw.tests.base import SlafwTestCase
from slafw.tests.mocks.motion_controller import MotionControllerMock


class TestTempSensors(SlafwTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.mcc = MotionControllerMock.get_6c()


class TestSL1UVTempSensor(TestTempSensors):
    def setUp(self) -> None:
        super().setUp()
        self.sensor = SL1TempSensorUV(self.mcc, HwConfig())

    def test_read_no_init(self):
        with self.assertRaises(UvTempSensorFailed):
            _ = self.sensor.value

    def test_read(self):
        callback = Mock(__name__="callback")
        self.sensor.value_changed.connect(callback)
        self.mcc.temps_changed.emit([11, 22, 33, 44])
        self.assertAlmostEqual(11, self.sensor.value)
        callback.assert_called_with(11)

    def test_overheat(self):
        callback = Mock(__name__="callback")
        self.sensor.overheat_changed.connect(callback)
        self.mcc.temps_changed.emit([11, 22, 33, 44])
        self.assertFalse(self.sensor.overheat)
        callback.assert_not_called()
        self.mcc.temps_changed.emit([56, 22, 33, 44])
        self.assertTrue(self.sensor.overheat)
        callback.assert_called_once()
        self.mcc.temps_changed.emit([54, 22, 33, 44])
        callback.assert_called_once()
        self.assertTrue(self.sensor.overheat)
        self.mcc.temps_changed.emit([40, 22, 33, 44])
        callback.assert_called_with(False)
        self.assertFalse(self.sensor.overheat)


class TestSL1SUVTempSensor(TestTempSensors):
    def setUp(self) -> None:
        super().setUp()
        self.sensor = SL1STempSensorUV(self.mcc, HwConfig())

    def test_sl1s_read(self):
        callback = Mock(__name__="callback")
        self.sensor.value_changed.connect(callback)
        self.mcc.temps_changed.emit([11, 22, 33, 44])
        self.assertAlmostEqual(33, self.sensor.value)
        callback.assert_called_with(33)


class TestSL1AmbientTempSensor(TestTempSensors):
    def setUp(self) -> None:
        super().setUp()
        self.sensor = SL1TempSensorAmbient(self.mcc)

    def test_ambient_read(self):
        callback = Mock(__name__="callback")
        self.sensor.value_changed.connect(callback)
        self.mcc.temps_changed.emit([11, 22, 33, 44])
        self.assertAlmostEqual(22, self.sensor.value)
        callback.assert_called_with(22)

    def test_ambient_fail(self):
        self.mcc.temps_changed.emit([0, -50, 0, 0])
        with self.assertRaises(TempSensorFailed):
            _ = self.sensor.value

    def test_ambient_fail_none(self):
        self.mcc.temps_changed.emit([0, None, 0, 0])
        with self.assertRaises(TempSensorFailed):
            _ = self.sensor.value
