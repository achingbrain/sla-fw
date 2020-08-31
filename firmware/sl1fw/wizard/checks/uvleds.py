# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Optional, List

from sl1fw.functions.checks import check_uv_leds
from sl1fw.libHardware import Hardware
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.base import SyncCheck, WizardCheckType
from sl1fw.wizard.setup import Configuration, Resource


class UVLEDsTest(SyncCheck):
    def __init__(self, hw: Hardware):
        super().__init__(
            WizardCheckType.UV_LEDS, Configuration(None, None), [Resource.UV],
        )
        self.hw = hw
        self.wizard_uv_voltage_row_1 = Optional[List[int]]
        self.wizard_uv_voltage_row_2 = Optional[List[int]]
        self.wizard_uv_voltage_row_3 = Optional[List[int]]

    def task_run(self, actions: UserActionBroker):
        row1, row2, row3 = check_uv_leds(self.hw, self._progress_callback)

        self.wizard_uv_voltage_row_1 = row1
        self.wizard_uv_voltage_row_2 = row2
        self.wizard_uv_voltage_row_3 = row3

    def _progress_callback(self, progress: float):
        self.progress = progress
