# This file is part of the SL1 firmware
# Copyright (C) 2020-2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from asyncio import sleep

from sl1fw.errors.errors import UVLEDsDisconnected, UVLEDsRowFailed, BoosterError
from sl1fw.libHardware import Hardware
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.base import WizardCheckType, DangerousCheck
from sl1fw.wizard.setup import Configuration, Resource


class UVLEDsTest_Booster(DangerousCheck):

    def __init__(self, hw: Hardware):
        super().__init__(
            hw, WizardCheckType.UV_LEDS, Configuration(None, None), [Resource.UV],
        )

    async def async_task_run(self, actions: UserActionBroker):
        await self.wait_cover_closed()
        await self.check_uv_leds()

    async def check_uv_leds(self):
        await self.wait_cover_closed()
        try: # check may be interrupted by another check or canceled
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
