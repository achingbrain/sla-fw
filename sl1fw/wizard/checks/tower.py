# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Optional

from sl1fw.functions.checks import tower_axis, tower_calibrate
from sl1fw.configs.hw import HwConfig
from sl1fw.libHardware import Hardware
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.base import SyncCheck, WizardCheckType
from sl1fw.wizard.setup import Configuration, Resource, TankSetup, PlatformSetup


class TowerHomeTest(SyncCheck):
    def __init__(self, hw: Hardware, hw_config: HwConfig):
        super().__init__(
            WizardCheckType.TOWER_HOME, Configuration(None, None), [Resource.TOWER, Resource.TOWER_DOWN],
        )
        self.hw = hw
        self.hw_config = hw_config

        self.wizard_tower_sensitivity = Optional[int]

    def task_run(self, actions: UserActionBroker):
        with actions.led_warn:
            self.wizard_tower_sensitivity = self.hw_config.towerSensitivity
            for _ in range(3):
                if not self.hw.towerSyncWait():
                    self.wizard_tower_sensitivity = self.hw.get_tower_sensitivity()


class TowerRangeTest(SyncCheck):
    def __init__(self, hw: Hardware, hw_config: HwConfig):
        super().__init__(
            WizardCheckType.TOWER_RANGE, Configuration(None, None), [Resource.TOWER, Resource.TOWER_DOWN],
        )
        self.hw = hw
        self.hw_config = hw_config

    def task_run(self, actions: UserActionBroker):
        with actions.led_warn:
            tower_axis(self.hw, self.hw_config)


class TowerAlignTest(SyncCheck):
    def __init__(self, hw: Hardware, hw_config: HwConfig):
        super().__init__(
            WizardCheckType.TOWER_CALIBRATION,
            Configuration(TankSetup.PRINT, PlatformSetup.PRINT),
            [Resource.TOWER, Resource.TOWER_DOWN],
        )
        self.hw = hw
        self.hw_config = hw_config

    def task_run(self, actions: UserActionBroker):
        # TODO: ensure cover closed
        with actions.led_warn:
            tower_calibrate(self.hw, self.hw_config, self._logger)
            # TODO: Allow to repeat align step on exception
