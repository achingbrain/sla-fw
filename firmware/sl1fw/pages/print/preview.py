# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from sl1fw import defines
from sl1fw.pages import page
from sl1fw.pages.print.base import PagePrintBase

if TYPE_CHECKING:
    from sl1fw.libDisplay import Display


@page
class PagePrintPreviewSwipe(PagePrintBase):
    Name = "printpreviewswipe"

    def __init__(self, display: Display):
        super(PagePrintPreviewSwipe, self).__init__(display)
        self.pageUI = "printpreviewswipe"

    def fillData(self):
        project = self.display.expo.project

        percReq = self.display.hw.calcPercVolume(project.used_material + defines.resinMinVolume)
        if percReq <= 100:
            resinVolumeText = _("Please fill the resin tank to at least %d %% and close the cover.") % percReq
        else:
            resinVolumeText = _(
                "Please fill the resin tank to the 100 % mark and close the cover.\n\n"
                "Resin will have to be added during this print job."
            )

        return {
            "name": project.name,
            "calibrationRegions": project.calibrate_regions,
            "date": project.modification_time,
            "layers": project.total_layers,
            "layer_height_first_mm": project.layer_height_first_nm / 1e6,
            "layer_height_mm": project.layer_height_nm / 1e6,
            "exposure_time_first_sec": project.exposure_time_first_ms / 1e3,
            "exposure_time_sec": project.exposure_time_ms / 1e3,
            "calibrate_time_sec": project.calibrate_time_ms / 1e3,
            "print_time_min": self.display.expo.countRemainTime(),
            "text": resinVolumeText,
        }

    def show(self):
        self.items.update(self.fillData())
        super(PagePrintPreviewSwipe, self).show()

    @staticmethod
    def changeButtonRelease():
        return "exposure"

    def contButtonRelease(self):
        self.display.expo.confirm_print_start()

    def backButtonRelease(self):
        self.display.expo.cancel()
        return "_BACK_"
