# This file is part of the SLA firmware
# Copyright (C) 2020-2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from asyncio import gather
from typing import Optional, Dict, Any

from slafw.errors.errors import ResinSensorFailed
from slafw.libHardware import Hardware
from slafw.wizard.actions import UserActionBroker
from slafw.wizard.checks.base import WizardCheckType, DangerousCheck
from slafw.wizard.setup import Configuration, TankSetup, PlatformSetup, Resource


class ResinSensorTest(DangerousCheck):
    allowed_min_mm = 4
    allowed_max_mm = 22

    def __init__(self, hw: Hardware):
        super().__init__(
            hw,
            WizardCheckType.RESIN_SENSOR,
            Configuration(TankSetup.PRINT, PlatformSetup.RESIN_TEST),
            [Resource.TOWER, Resource.TOWER_DOWN],
        )
        self.position_mm: Optional[float] = None

    async def async_task_run(self, actions: UserActionBroker):
        await self.wait_cover_closed()
        with actions.led_warn:
            await gather(self._hw.verify_tower(), self._hw.verify_tilt())
            self._hw.set_tower_position_nm(120_000_000)
            position_mm = await self._hw.get_resin_sensor_position_mm()
            self._logger.debug("resin triggered at %s mm", position_mm)

            # Move tower up to default position, move now in case of exception
            await self._hw.verify_tower()

            # to work properly even with loosen rocker bearing
            if not self.allowed_min_mm <= position_mm <= self.allowed_max_mm:
                raise ResinSensorFailed(position_mm)
            self.position_mm = position_mm

    def get_result_data(self) -> Dict[str, Any]:
        return {"wizardResinTriggeredMM": self.position_mm}
