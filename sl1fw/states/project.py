# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from enum import unique, Enum


@unique
class ProjectErrors(Enum):
    NONE = 0
    NOT_FOUND = 1
    CANT_READ = 2
    NOT_ENOUGH_LAYERS = 3
    CORRUPTED = 4
    ANALYSIS_FAILED = 5
    CALIBRATION_INVALID = 6

@unique
class ProjectWarnings(Enum):
    PRINT_DIRECTLY = 1
    ALTERED_VALUES = 2
    PER_PARTES_NOAVAIL = 3
    MASK_NOAVAIL = 4
    TRUNCATED = 5

@unique
class LayerCalibrationType(Enum):
    NONE = 0
    LABEL_PAD = 1
    LABEL_TEXT = 2
