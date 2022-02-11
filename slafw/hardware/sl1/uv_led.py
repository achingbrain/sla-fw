# This file is part of the SLA firmware
# Copyright (C) 2022 Prusa Research a.s - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import List

from slafw.hardware.printer_model import PrinterModel
from slafw.hardware.uv_led import UvLed
from slafw.motion_controller.controller import MotionController


class UvLedSL1(UvLed):
    def __init__(self, mcc: MotionController, printer_model: PrinterModel):
        self._mcc = mcc
        super().__init__(printer_model)


    @property
    def _is500khz(self) -> bool:
        # FIXME this will not work for board "7a"
        return self._mcc.board["revision"] >= 6 and self._mcc.board["subRevision"] == "c"

    @property
    def get_check_pwms(self) -> List[int]:
        if self._is500khz:
            return [40, 122, 243, 250]  # board rev 0.6c+
        return [31, 94, 188, 219]  # board rev. < 0.6c
