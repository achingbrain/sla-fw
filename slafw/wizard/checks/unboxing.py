# This file is part of the SLA firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from asyncio import sleep
from typing import Optional

from slafw.hardware.base.hardware import BaseHardware
from slafw.wizard.actions import UserActionBroker
from slafw.wizard.checks.base import WizardCheckType, Check
from slafw.wizard.setup import Configuration, Resource


class MoveToFoam(Check):
    FOAM_TARGET_POSITION_NM = 30_000_000

    def __init__(self, hw: BaseHardware):
        super().__init__(
            WizardCheckType.MOVE_TO_FOAM, Configuration(None, None), [Resource.TOWER_DOWN, Resource.TOWER],
        )
        self.result: Optional[bool] = None
        self.hw = hw

    async def async_task_run(self, actions: UserActionBroker):
        with actions.led_warn:
            self.hw.set_tower_position_nm(0)
            self.hw.setTowerProfile("homingFast")
            initial_pos_nm = self.hw.tower_position_nm
            self.hw.tower_position_nm = self.FOAM_TARGET_POSITION_NM
            while self.hw.isTowerMoving():
                if self.FOAM_TARGET_POSITION_NM != initial_pos_nm:
                    self.progress = (self.hw.tower_position_nm - initial_pos_nm) / (
                        self.FOAM_TARGET_POSITION_NM - initial_pos_nm
                    )
                else:
                    self.progress = 1
                await sleep(0.5)
            self.hw.motorsRelease()


class MoveToTank(Check):
    def __init__(self, hw: BaseHardware):
        super().__init__(
            WizardCheckType.MOVE_TO_TANK, Configuration(None, None), [Resource.TOWER_DOWN, Resource.TOWER],
        )
        self.result: Optional[bool] = None
        self.hw = hw

    async def async_task_run(self, actions: UserActionBroker):
        with actions.led_warn:
            await self.hw.towerSyncWaitAsync(retries=3)  # Let this fail fast, allow for proper tower synced check
            self.hw.motorsRelease()
