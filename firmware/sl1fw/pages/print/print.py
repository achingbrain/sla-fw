# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from datetime import datetime, timezone
from time import time
from typing import TYPE_CHECKING

from sl1fw.libExposure import Exposure
from sl1fw.pages import page
from sl1fw.pages.print.action import PagePrintActionPending
from sl1fw.pages.print.base import PagePrintBase

if TYPE_CHECKING:
    from sl1fw.libDisplay import Display


@page
class PagePrint(PagePrintBase):
    Name = "print"

    def __init__(self, display: Display):
        super().__init__(display)
        self.pageUI = "print"
        self.totalHeight = None
        self.lastLayer = None
        self.last_expo_end = None

    def prepare(self):
        self.lastLayer = 0
        if self.display.expo.in_progress:
            return

        self.display.expo.prepare()
        self.display.pages["finished"].data = None

    def callback(self):
        # Update exposure end
        if self.display.expo.exposure_end and self.display.expo.exposure_end != self.last_expo_end:
            diff = self.display.expo.exposure_end - \
                datetime.now(tz=timezone.utc)
            self.showItems(exposure=diff.seconds + diff.microseconds / 1000000)
            self.last_expo_end = self.display.expo.exposure_end

        if self.lastLayer != self.display.expo.actualLayer:
            self._layer_update(self.display.expo)

        return super().callback()

    def _layer_update(self, expo: Exposure):
        self.lastLayer = expo.actualLayer
        project = self.display.expo.project

        time_remain_min = expo.countRemainTime()
        time_elapsed_min = int(round((time() - expo.printStartTime) / 60))
        percent = int(100 * self.display.expo.progress)

        if expo.warn_resin:
            self.display.hw.beepAlarm(1)
        fansRpm = self.display.hw.getFansRpm()
        self.showItems(
            time_remain_min=time_remain_min,
            time_elapsed_min=time_elapsed_min,
            current_layer=self.lastLayer,
            total_layers=project.totalLayers,
            project_name=project.name,
            progress=percent,
            resin_used_ml=expo.resinCount,
            resin_remaining_ml=expo.remain_resin_ml,
            temp_cpu=self.display.hw.getCpuTemperature(),
            temp_led=self.display.hw.getUvLedTemperature(),
            temp_amb=self.display.hw.getAmbientTemperature(),
            uv_led_fan=fansRpm[0],
            blower_fan=fansRpm[1],
            rear_fan=fansRpm[2],
            cover_closed=self.display.hw.isCoverClosed(),
        )

    def show(self):
        self.items.update({"show_admin": self.display.runtime_config.show_admin})
        super(PagePrint, self).show()

    def feedmeButtonRelease(self):
        self.display.pages["yesno"].setParams(yesFce=self.doFeedme, text=_("Do you really want to add resin into the tank?"))
        return "yesno"

    def doFeedme(self):
        self.display.expo.doFeedMe()
        return PagePrintActionPending.Name

    def updownButtonRelease(self):
        self.display.pages["yesno"].setParams(
            yesFce=self.doUpAndDown,
            text=_(
                "Do you really want the platform to go up and down?\n\n" "It may affect the printed object!"),
        )
        return "yesno"

    def doUpAndDown(self):
        self.display.expo.doUpAndDown()
        return PagePrintActionPending.Name

    @staticmethod
    def settingsButtonRelease():
        return "exposure"

    def turnoffButtonRelease(self, hw_button=False):
        if hw_button:
            self.display.pages["yesno"].setParams(
                yesFce=self.exitPrint,
                text=_("Do you really want to cancel the current job?"))
            return "yesno"

        return self.exitPrint("_SELF_")

    def adminButtonRelease(self):
        if self.display.runtime_config.show_admin:
            return "admin"
        return None
