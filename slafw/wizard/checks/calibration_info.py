# This file is part of the SLA firmware
# Copyright (C) 2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

from slafw.configs.hw import HwConfig
from slafw.wizard.actions import UserActionBroker
from slafw.wizard.checks.base import Check, WizardCheckType
from slafw.wizard.setup import Configuration


@dataclass
class CheckData:
    tiltHeight: int
    tower_height_nm: int


class CalibrationInfo(Check):
    def __init__(self, hw_config: HwConfig):
        super().__init__(
            WizardCheckType.CALIBRATION_INFO, Configuration(None, None), [],
        )
        self._hw_config = hw_config
        self._result_data: Optional[CheckData] = None

    async def async_task_run(self, actions: UserActionBroker):
        self._logger.debug("Obtaining calibration information")
        self._result_data = CheckData(self._hw_config.tiltHeight, self._hw_config.tower_height_nm)

    def get_result_data(self) -> Dict[str, Any]:
        return asdict(self._result_data)
