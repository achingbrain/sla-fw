# This file is part of the SL1 firmware
# Copyright (C) 2020-2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from asyncio import sleep
from typing import Optional, Dict, Any

from sl1fw import test_runtime, defines
from sl1fw.errors.errors import ResinFailed
from sl1fw.libHardware import Hardware
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.base import WizardCheckType, DangerousCheck
from sl1fw.wizard.setup import Configuration, TankSetup, PlatformSetup, Resource


class ResinSensorTest(DangerousCheck):
    def __init__(self, hw: Hardware):
        super().__init__(
            hw,
            WizardCheckType.RESIN_SENSOR,
            Configuration(TankSetup.PRINT, PlatformSetup.RESIN_TEST),
            [Resource.TOWER, Resource.TOWER_DOWN],
        )

        self.volume_ml: Optional[float] = None

    async def async_task_run(self, actions: UserActionBroker):
        await self.wait_cover_closed()
        with actions.led_warn:
            await self._hw.towerSyncWaitAsync()
            self._hw.setTowerPosition(self._hw.config.calcMicroSteps(defines.defaultTowerHeight))
            volume_ml = self._hw.getResinVolume()
            self._logger.debug("resin volume: %s", volume_ml)
            if (
                not defines.resinWizardMinVolume <= volume_ml <= defines.resinWizardMaxVolume
            ) and not test_runtime.testing:  # to work properly even with loosen rocker bearing
                raise ResinFailed(volume_ml)

            self._hw.towerSync()
            await self._hw.tilt.sync_wait_coroutine()
            while self._hw.isTowerMoving():
                await sleep(0.25)
            self._hw.motorsRelease()
            self._hw.stopFans()

            self.volume_ml = volume_ml

    def get_result_data(self) -> Dict[str, Any]:
        return {"wizardResinVolume": self.volume_ml}
