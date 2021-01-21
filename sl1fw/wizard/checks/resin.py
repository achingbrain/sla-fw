# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Optional

from sl1fw.functions.checks import resin_sensor
from sl1fw.configs.hw import HwConfig
from sl1fw.libHardware import Hardware
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.base import WizardCheckType, SyncCheck
from sl1fw.wizard.setup import Configuration, TankSetup, PlatformSetup, Resource


class ResinSensorTest(SyncCheck):
    def __init__(self, hw: Hardware, hw_config: HwConfig):
        super().__init__(
            WizardCheckType.RESIN_SENSOR,
            Configuration(TankSetup.PRINT, PlatformSetup.RESIN_TEST),
            [Resource.TOWER, Resource.TOWER_DOWN],
        )
        self.hw = hw
        self.hw_config = hw_config

        self.wizard_resin_volume_ml: Optional[float] = None

    def task_run(self, actions: UserActionBroker):
        with actions.led_warn:
            self.wizard_resin_volume_ml = resin_sensor(self.hw, self.hw_config, self._logger)
