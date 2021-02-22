# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Optional, Dict, Any

from sl1fw.functions.checks import tower_axis, tower_calibrate
from sl1fw.configs.hw import HwConfig
from sl1fw.libHardware import Hardware
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.base import WizardCheckType, SyncDangerousCheck
from sl1fw.wizard.setup import Configuration, Resource, TankSetup, PlatformSetup


class TowerHomeTest(SyncDangerousCheck):
    def __init__(self, hw: Hardware, hw_config: HwConfig):
        super().__init__(
            hw, WizardCheckType.TOWER_HOME, Configuration(None, None), [Resource.TOWER, Resource.TOWER_DOWN],
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

    def get_result_data(self) -> Dict[str, Any]:
        return {
            # measured fake resin volume in wizard (without resin with rotated platform)
            "towerSensitivity": self.wizard_tower_sensitivity
        }


class TowerRangeTest(SyncDangerousCheck):
    def __init__(self, hw: Hardware, hw_config: HwConfig):
        super().__init__(
            hw, WizardCheckType.TOWER_RANGE, Configuration(None, None), [Resource.TOWER, Resource.TOWER_DOWN],
        )
        self.hw = hw
        self.hw_config = hw_config

    def task_run(self, actions: UserActionBroker):
        self.wait_cover_closed_sync()
        with actions.led_warn:
            tower_axis(self.hw, self.hw_config)


class TowerAlignTest(SyncDangerousCheck):
    def __init__(self, hw: Hardware, hw_config: HwConfig):
        super().__init__(
            hw,
            WizardCheckType.TOWER_CALIBRATION,
            Configuration(TankSetup.PRINT, PlatformSetup.PRINT),
            [Resource.TOWER, Resource.TOWER_DOWN],
        )
        self.hw = hw
        self.hw_config = hw_config
        self._tower_height = None

    def task_run(self, actions: UserActionBroker):
        self.wait_cover_closed_sync()
        with actions.led_warn:
            self._tower_height = tower_calibrate(self.hw, self.hw_config, self._logger)
            # TODO: Allow to repeat align step on exception

    def get_result_data(self) -> Dict[str, Any]:
        return {"towerHeight": self._tower_height}
