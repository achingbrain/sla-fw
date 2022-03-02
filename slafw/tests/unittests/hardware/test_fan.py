# This file is part of the SLA firmware
# Copyright (C) 2022 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
from abc import ABC, abstractmethod
from functools import cached_property
from threading import Thread
from time import sleep
from typing import Optional
from unittest.mock import Mock, patch

from slafw.configs.hw import HwConfig
from slafw.hardware.base.fan import Fan
from slafw.hardware.sl1.fan import SL1FanUVLED, SL1FanBlower, SL1FanRear
from slafw.tests.base import SlafwTestCase
from slafw.tests.mocks.motion_controller import MotionControllerMock
from slafw.tests.mocks.temp_sensor import MockTempSensor


class TestFan(Fan):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._target_rpm = 0

    @property
    def enabled(self) -> bool:
        return True

    @property
    def rpm(self) -> int:
        return self.target_rpm

    @property
    def error(self) -> bool:
        return False

    @property
    def target_rpm(self) -> int:
        return self._target_rpm

    @target_rpm.setter
    def target_rpm(self, value: int):
        self._target_rpm = value


@patch("slafw.hardware.base.fan.Fan.AUTO_CONTROL_INTERVAL_S", 0.2)
class TestBaseFan(SlafwTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.temp_value = Mock(return_value=12)
        self.inhibitor_value = Mock(return_value=False)
        self.temp = MockTempSensor("Fake temp", 10, 20, mock_value=self.temp_value)
        self.fan = TestFan("Test", 1000, 2000, 1500, reference=self.temp, auto_control_inhibitor=self.inhibitor_value)

        self._thread = Thread(target=self._run_components)
        self._task: Optional[asyncio.Task] = None
        self._thread.start()

    def tearDown(self) -> None:
        self._task.cancel()
        self._thread.join()
        super().tearDown()

    def _run_components(self):
        asyncio.run(self._run_components_async())

    async def _run_components_async(self):
        self._task = asyncio.create_task(self.fan.run())
        await self._task

    def test_auto_control(self):
        self.temp_value.return_value = self.temp.max
        sleep(1)
        self.assertEqual(self.fan.max_rpm, self.fan.target_rpm)

        self.temp_value.return_value = self.temp.min
        sleep(1)
        self.assertEqual(self.fan.min_rpm, self.fan.target_rpm)

        self.temp_value.return_value = (self.temp.min + self.temp.max) / 2
        sleep(1)
        self.assertEqual((self.fan.min_rpm + self.fan.max_rpm) / 2, self.fan.target_rpm)

    def test_auto_control_disable(self):
        rpm = self.fan.target_rpm
        self.fan.auto_control = False
        self.temp_value.return_value = self.temp.max
        sleep(1)
        self.assertEqual(rpm, self.fan.target_rpm)

        self.fan.auto_control = True
        sleep(1)
        self.assertEqual(self.fan.max_rpm, self.fan.target_rpm)

    def test_auto_control_inhibit(self):
        rpm = self.fan.target_rpm
        self.inhibitor_value.return_value = True
        self.temp_value.return_value = self.temp.max
        sleep(1)
        self.assertEqual(rpm, self.fan.target_rpm)

        self.inhibitor_value.return_value = False
        sleep(2)
        self.assertEqual(self.fan.max_rpm, self.fan.target_rpm)


class DoNotRunTestDirectlyFromBaseClass:
    # pylint: disable = too-few-public-methods
    class BaseSL1FanTest(SlafwTestCase, ABC):
        @cached_property
        @abstractmethod
        def fan(self) -> Fan:
            ...

        @cached_property
        @abstractmethod
        def index(self) -> int:
            ...

        def setUp(self) -> None:
            super().setUp()
            self.config = HwConfig()
            self.mcc = MotionControllerMock.get_6c()
            self.temp = MockTempSensor("Fake temp", 10, 20, mock_value=Mock(return_value=20))

        def test_rpm_set(self):
            self.fan.target_rpm = 1000
            self.mcc.set_fan_rpm.assert_called_with(self.index, 1000)

        def test_enable_set(self):
            self.fan.enabled = False
            self.mcc.set_fan_enabled.assert_called_with(self.index, False)
            self.fan.enabled = True
            self.mcc.set_fan_enabled.assert_called_with(self.index, True)

        def test_rpm_read(self):
            callback = Mock(__name__="callback")
            self.fan.rpm_changed.connect(callback)
            rpms = (1111, 2222, 3333)
            self.mcc.fans_rpm_changed.emit(rpms)
            self.assertEqual(rpms[self.index], self.fan.rpm)
            callback.assert_called_with(rpms[self.index])

        def test_error_read(self):
            callback = Mock(__name__="callback")
            self.fan.error_changed.connect(callback)

            self.mcc.fans_error_changed.emit([i == self.index for i in range(3)])
            self.assertEqual(True, self.fan.error)
            callback.assert_called_with(True)

            self.mcc.fans_error_changed.emit([i != self.index for i in range(3)])
            self.assertEqual(False, self.fan.error)
            callback.assert_called_with(False)


class TestSL1FanUVLEDX(DoNotRunTestDirectlyFromBaseClass.BaseSL1FanTest):
    @cached_property
    def fan(self) -> Fan:
        return SL1FanUVLED(self.mcc, self.config, reference=self.temp)

    @cached_property
    def index(self) -> int:
        return 0


class TestSL1FanBlower(DoNotRunTestDirectlyFromBaseClass.BaseSL1FanTest):
    @cached_property
    def fan(self) -> Fan:
        return SL1FanBlower(self.mcc, self.config)

    @cached_property
    def index(self) -> int:
        return 1


class TestSL1FanRear(DoNotRunTestDirectlyFromBaseClass.BaseSL1FanTest):
    @cached_property
    def fan(self) -> Fan:
        return SL1FanRear(self.mcc, self.config)

    @cached_property
    def index(self) -> int:
        return 2
