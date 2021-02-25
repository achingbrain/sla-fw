# This file is part of the SL1 firmware
# Copyright (C) 2020-2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass, asdict
from typing import List, Dict, Any

from sl1fw.configs.hw import HwConfig
from sl1fw.functions.checks import check_uv_leds
from sl1fw.libHardware import Hardware
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.base import WizardCheckType, SyncDangerousCheck
from sl1fw.wizard.setup import Configuration, Resource


@dataclass
class CheckData:
    # data in mV for 1/6, 1/2, 1/1 of max PWM for MC board
    wizardUvVoltageRow1: List[int]
    # data in mV for 1/6, 1/2, 1/1 of max PWM for MC board
    wizardUvVoltageRow2: List[int]
    # data in mV for 1/6, 1/2, 1/1 of max PWM for MC board
    wizardUvVoltageRow3: List[int]

    # UV PWM set during this check
    uvPwm: int


class UVLEDsTest(SyncDangerousCheck):
    def __init__(self, hw: Hardware, hw_config: HwConfig):
        super().__init__(
            hw, WizardCheckType.UV_LEDS, Configuration(None, None), [Resource.UV],
        )
        self._hw = hw
        self._hw_config = hw_config

        self._result_data = None

    def task_run(self, actions: UserActionBroker):
        self.wait_cover_closed()
        row1, row2, row3 = check_uv_leds(self._hw, self._progress_callback)
        self._result_data = CheckData(row1, row2, row3, self._hw_config.uvPwm)

    def _progress_callback(self, progress: float):
        self.progress = progress

    def get_result_data(self) -> Dict[str, Any]:
        return asdict(self._result_data)
