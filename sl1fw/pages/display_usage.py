# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import os

import numpy
from PIL import Image
from prusaerrors.sl1.codes import Sl1Codes

from sl1fw import defines
from sl1fw.pages import page
from sl1fw.pages.base import Page


@page
class PageDisplayUsage(Page):
    Name = "displayusage"

    def __init__(self, display):
        super(PageDisplayUsage, self).__init__(display)
        self.pageUI = "picture"
        self.pageTitle = "Display usage heatmap"
        self.palette = None
        try:
            palette_bytes = bytes()
            with open(defines.displayUsagePalette, "r") as f:
                for line in f:
                    palette_bytes += bytes.fromhex(line.strip()[1:])
            self.palette = list(palette_bytes)
        except Exception:
            self.logger.exception("load palette failed")

    def prepare(self):
        try:
            with numpy.load(defines.displayUsageData) as npzfile:
                saved_data = npzfile["display_usage"]

        except Exception:
            self.logger.exception("load display usage failed")
            saved_data = None

        if saved_data is None:
            self.logger.error("No display suage data to show")
            self.display.pages["error"].setParams(code=Sl1Codes.NO_DISPLAY_USAGE_DATA.raw_code)
            return "error"

        if saved_data.shape != self.display.exposure_image.display_usage_size:
            self.logger.warning("Wrong saved data shape: %s", saved_data.shape)
            self.display.pages["error"].setParams(code=Sl1Codes.NO_DISPLAY_USAGE_DATA.raw_code)
            return "error"

        image_path = os.path.join(defines.ramdiskPath, "displayhm.png")
        self.generateDisplayUsageHeatmap(image_path, saved_data)
        self.setItems(image_path="file://%s" % image_path)
        return None

    def generateDisplayUsageHeatmap(self, filename, data):
        max_value = data.max()
        # 0-255 range
        data = data * 255 / max_value
        image = Image.fromarray(data.astype("int8"), "P")
        if self.palette:
            image.putpalette(self.palette)

        trans = image.transpose(Image.ROTATE_270)
        trans.save(filename)

    @staticmethod
    def _EXIT_():
        return "_EXIT_"

    @staticmethod
    def _BACK_():
        return "_BACK_"
