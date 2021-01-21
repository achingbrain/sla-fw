# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Optional

from sl1fw.functions.checks import check_uv_fans
from sl1fw.configs.hw import HwConfig
from sl1fw.libHardware import Hardware
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.base import SyncCheck, WizardCheckType
from sl1fw.wizard.setup import Configuration, Resource


class UVFansTest(SyncCheck):
    def __init__(self, hw: Hardware, hw_config: HwConfig):
        super().__init__(
            WizardCheckType.UV_FANS, Configuration(None, None), [Resource.FANS, Resource.UV],
        )
        self.hw = hw
        self.hw_config = hw_config

        self.wizard_uv_fan_avg_rpm: Optional[int] = None
        self.wizard_uv_temp_warm: Optional[float] = None

    def task_run(self, actions: UserActionBroker):
        avg_rpms, uv_temp = check_uv_fans(
            self.hw, self.hw_config, self._logger, progress_callback=self._progress_callback
        )

        self.wizard_uv_fan_avg_rpm = avg_rpms
        self.wizard_uv_temp_warm = uv_temp

    def _progress_callback(self, progress: float):
        self.progress = progress
