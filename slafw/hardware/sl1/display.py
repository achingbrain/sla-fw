# This file is part of the SLA firmware
# Copyright (C) 2022 Prusa Research a.s - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later
import os

from slafw import defines

from slafw.hardware.base.display import PrintDisplay
from slafw.motion_controller.controller import MotionController


class PrintDisplaySL1(PrintDisplay):
    def __init__(self, mcc: MotionController):
        self._mcc = mcc
        super().__init__()
        self._mcc.statistics_changed.connect(self._on_statistics_changed)

    def start_counting_usage(self):
        self._mcc.do("!ulcd", 1)

    def stop_counting_usage(self):
        self._mcc.do("!ulcd", 0)

    @property
    def usage_s(self) -> int:
        data = self._mcc.doGetIntList("?usta")  # time counter [s] #TODO add uv average current, uv average temperature
        if len(data) != 2:
            raise ValueError(f"UV statistics data count not match! ({data})")
        return data[1]

    def save_usage(self):
        self._mcc.do("!usta", 0)

    def clear_usage(self):
        """
        Call if print display was replaced
        """
        self._mcc.do("!usta", 2)
        try:
            os.remove(defines.displayUsageData)
        except FileNotFoundError:
            pass

    def _on_statistics_changed(self, data):
        self.usage_s_changed.emit(data[1])
