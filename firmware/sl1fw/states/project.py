# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from enum import unique, Enum


@unique
class ProjectState(Enum):
    UNINITIALIZED = -1
    OK = 0
    NOT_FOUND = 1
    CANT_READ = 2
    NOT_ENOUGH_LAYERS = 3
    CORRUPTED = 4
    PRINT_DIRECTLY = 5
