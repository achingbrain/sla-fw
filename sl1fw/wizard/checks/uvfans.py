# This file is part of the SL1 firmware
# Copyright (C) 2020-2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass, asdict
from typing import Dict, Any

from sl1fw.configs.hw import HwConfig
from sl1fw.functions.checks import check_uv_fans
from sl1fw.libHardware import Hardware
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.base import WizardCheckType, SyncDangerousCheck
from sl1fw.wizard.setup import Configuration, Resource


@dataclass
class CheckData:
    # fans RPM when using default PWM
    wizardFanRpm: list
    # UV LED temperature at the beginning of test (should be close to ambient)
    wizardTempUvWarm: float


class UVFansTest(SyncDangerousCheck):
    def __init__(self, hw: Hardware, hw_config: HwConfig):
        super().__init__(
            hw, WizardCheckType.UV_FANS, Configuration(None, None), [Resource.FANS, Resource.UV],
        )
        self.hw = hw
        self.hw_config = hw_config

        self._check_data = None

    def task_run(self, actions: UserActionBroker):
        self.wait_cover_closed_sync()
        avg_rpms, uv_temp = check_uv_fans(
            self.hw, self.hw_config, self._logger, progress_callback=self._progress_callback
        )

        self._check_data = CheckData(avg_rpms, uv_temp)

    def _progress_callback(self, progress: float):
        self.progress = progress

    def get_result_data(self) -> Dict[str, Any]:
        return asdict(self._check_data)
