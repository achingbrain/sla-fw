# This file is part of the SLA firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from enum import Enum


class LogsState(Enum):
    IDLE = 0
    EXPORTING = 1
    SAVING = 2
    FINISHED = 3
    FAILED = 4
    CANCELED = 5

    @staticmethod
    def finished_states():
        return {LogsState.FINISHED, LogsState.CANCELED, LogsState.FAILED}


class StoreType(Enum):
    IDLE = 0
    USB = 1
    UPLOAD = 2
