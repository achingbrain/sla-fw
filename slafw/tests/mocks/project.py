# This file is part of the SLA firmware
# Copyright (C) 2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from PySignal import Signal


class Project:
    # pylint: disable = too-few-public-methods
    # pylint: disable = too-many-instance-attributes
    def __init__(self):
        self.path_changed = Signal()
        self.exposure_user_profile = 0
        self.used_material_nl = 45242420
        self.total_layers = 4242
        self.layer_height_nm = 50000
        self.layer_height_first_nm = self.layer_height_nm
        self.total_height_nm = self.total_layers * self.layer_height_nm
        self.name = "Fake name"
        self.path = "/project.sl1"
        self.exposure_time_ms = 1000
        self.exposure_time_first_ms = self.exposure_time_ms
        self.calibrate_time_ms = 0
        self.calibrate_regions = 0
