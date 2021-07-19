# This file is part of the SL1 firmware
# Copyright (C) 2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

import distro

from sl1fw.libHardware import Hardware
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.base import Check, WizardCheckType
from sl1fw.wizard.setup import Configuration


@dataclass
class CheckData:
    # pylint: disable = too-many-instance-attributes
    # following values are for quality monitoring systems
    osVersion: str
    a64SerialNo: str
    mcSerialNo: str
    mcFwVersion: str
    mcBoardRev: str
    uvLedCounter_s: int
    displayCounter_s: int
    model: str


class SystemInfoTest(Check):
    def __init__(self, hw: Hardware):
        super().__init__(
            WizardCheckType.SYS_INFO, Configuration(None, None), [],
        )
        self._hw = hw
        self._result_data: Optional[CheckData] = None

    async def async_task_run(self, actions: UserActionBroker):
        self._logger.debug("Obtaining system information")

        uv_led, display = self._hw.getUvStatistics()
        self._result_data = CheckData(
            distro.version(),
            self._hw.cpuSerialNo,
            self._hw.mcSerialNo,
            self._hw.mcFwVersion,
            self._hw.mcBoardRevision,
            uv_led,
            display,
            self._hw.printer_model.name,
        )

    def get_result_data(self) -> Dict[str, Any]:
        return asdict(self._result_data)
