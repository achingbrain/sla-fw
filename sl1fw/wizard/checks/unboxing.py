# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from time import sleep
from typing import Optional

from sl1fw.libHardware import Hardware
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.base import WizardCheckType, SyncCheck
from sl1fw.wizard.setup import Configuration, Resource


class MoveToFoam(SyncCheck):
    FOAM_TARGET_POSITION_NM = 30_000_000

    def __init__(self, hw: Hardware):
        super().__init__(
            WizardCheckType.MOVE_TO_FOAM, Configuration(None, None), [Resource.TOWER_DOWN, Resource.TOWER],
        )
        self.result: Optional[bool] = None
        self.hw = hw

    def task_run(self, actions: UserActionBroker):
        with actions.led_warn:
            self.hw.setTowerPosition(0)
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
                sleep(0.5)
            self.hw.motorsRelease()


class MoveToTank(SyncCheck):
    def __init__(self, hw: Hardware):
        super().__init__(
            WizardCheckType.MOVE_TO_TANK, Configuration(None, None), [Resource.TOWER_DOWN, Resource.TOWER],
        )
        self.result: Optional[bool] = None
        self.hw = hw

    def task_run(self, actions: UserActionBroker):
        with actions.led_warn:
            self.hw.towerSyncWait(retries=3)  # Let this fail fast, allow for proper tower synced check
            self.hw.motorsRelease()
