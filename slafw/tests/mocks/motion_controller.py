# This file is part of the SLA firmware
# Copyright (C) 2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from PySignal import Signal


class MotionControllerMock:
    def __init__(self, revision: int, subrevision: str):
        self.board = {"revision": revision, "subRevision": subrevision}
        self.temps_changed = Signal()
        self.value_refresh_failed = Signal()

    @staticmethod
    def get_5a():
        return MotionControllerMock(5, "a")

    @staticmethod
    def get_6c():
        return MotionControllerMock(6, "c")
