# This file is part of the SL1 firmware
# Copyright (C) 2020-2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from abc import abstractmethod
from asyncio import sleep
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

from sl1fw import test_runtime
from sl1fw.errors.errors import UVLEDsDisconnected, UVLEDsRowFailed, BoosterError
from sl1fw.errors.errors import UVLEDsVoltagesDifferTooMuch
from sl1fw.functions.checks import get_uv_check_pwms
from sl1fw.libHardware import Hardware
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.base import WizardCheckType, DangerousCheck
from sl1fw.wizard.setup import Configuration, Resource


class UVLEDsTest(DangerousCheck):
    @abstractmethod
    async def async_task_run(self, actions: UserActionBroker):
        ...

    @staticmethod
    def get_test(hw: Hardware) -> UVLEDsTest:
        """
        Instantiate UV LEDs test for particular printer HW
        """
        if hw.printer_model.options.has_booster:
            return UVLEDsTestBooster(hw)

        return UVLEDsTestVoltages(hw)


class UVLEDsTestBooster(UVLEDsTest):
    def __init__(self, hw: Hardware):
        super().__init__(
            hw,
            WizardCheckType.UV_LEDS,
            Configuration(None, None),
            [Resource.UV],
        )

    async def async_task_run(self, actions: UserActionBroker):
        await self.wait_cover_closed()
        await self.check_uv_leds()

    async def check_uv_leds(self):
        await self.wait_cover_closed()
        try:  # check may be interrupted by another check or canceled
            # test DAC output comparator
            self._hw.uvLedPwm = 40
            await sleep(0.25)
            dac_state, led_states = self._hw.sl1s_booster.status()
            if dac_state:
                raise BoosterError("DAC not turned off")
            self._hw.uvLedPwm = 80
            await sleep(0.25)
            dac_state, led_states = self._hw.sl1s_booster.status()
            if not dac_state:
                raise BoosterError("DAC not turned on")
            # test LED status
            self._hw.uvLedPwm = 20
            self._hw.uvLed(True)
            await sleep(0.5)
            dac_state, led_states = self._hw.sl1s_booster.status()
            if all(led_states):
                raise UVLEDsDisconnected()
            if any(led_states):
                raise UVLEDsRowFailed()
        finally:
            self._hw.uvLed(False)


@dataclass
class CheckData:
    # data in mV for 1/6, 1/2, 1/1 of max PWM for MC board
    wizardUvVoltageRow1: List[int]
    # data in mV for 1/6, 1/2, 1/1 of max PWM for MC board
    wizardUvVoltageRow2: List[int]
    # data in mV for 1/6, 1/2, 1/1 of max PWM for MC board
    wizardUvVoltageRow3: List[int]

    # UV PWM set during this check
    uvPwm: int


class UVLEDsTestVoltages(UVLEDsTest):
    CHECK_UV_PWM_INDEXES = 3

    def __init__(self, hw: Hardware):
        super().__init__(
            hw,
            WizardCheckType.UV_LEDS,
            Configuration(None, None),
            [Resource.UV],
        )
        self._result_data: Optional[CheckData] = None

    async def async_task_run(self, actions: UserActionBroker):
        await self.wait_cover_closed()
        row1, row2, row3 = await self.check_uv_leds()
        self._result_data = CheckData(row1, row2, row3, self._hw.config.uvPwm)

    def get_result_data(self) -> Dict[str, Any]:
        return asdict(self._result_data)

    async def check_uv_leds(self):
        await self.wait_cover_closed()
        self._hw.uvLedPwm = 0
        self._hw.uvLed(True)
        uv_pwms = get_uv_check_pwms(self._hw)

        diff = 0.55  # [mV] voltages in all rows cannot differ more than this limit
        row1 = list()
        row2 = list()
        row3 = list()
        try:  # check may be interrupted by another check or canceled
            for i in range(self.CHECK_UV_PWM_INDEXES):
                self.progress = i / self.CHECK_UV_PWM_INDEXES
                self._hw.uvLedPwm = uv_pwms[i]
                if not test_runtime.testing:
                    await sleep(5)  # wait to refresh all voltages (board rev. 0.6+)
                volts = list(self._hw.getVoltages())
                del volts[-1]  # delete power supply voltage
                self._logger.info("UV voltages: %s", volts)
                if max(volts) - min(volts) > diff and not test_runtime.testing:
                    raise UVLEDsVoltagesDifferTooMuch(f"{max(volts) - min(volts)} (max - min) > {diff}")
                row1.append(int(volts[0] * 1000))
                row2.append(int(volts[1] * 1000))
                row3.append(int(volts[2] * 1000))
        finally:
            self._hw.uvLed(False)

        return row1, row2, row3
