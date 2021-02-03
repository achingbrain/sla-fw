# This file is part of the SL1 firmware
# Copyright (C) 2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass, asdict
from typing import Dict, Any

from sl1fw.configs.hw import HwConfig
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.base import Check, WizardCheckType
from sl1fw.wizard.setup import Configuration


@dataclass
class CheckData:
    tiltHeight: int
    towerHeight: int


class CalibrationInfo(Check):
    def __init__(self, hw_config: HwConfig):
        super().__init__(
            WizardCheckType.CALIBRATION_INFO, Configuration(None, None), [],
        )
        self._hw_config = hw_config
        self._result_data = None

    async def async_task_run(self, actions: UserActionBroker):
        self._logger.debug("Obtaining calibration information")
        self._result_data = CheckData(self._hw_config.tiltHeight, self._hw_config.towerHeight)

    def get_result_data(self) -> Dict[str, Any]:
        return asdict(self._result_data)
