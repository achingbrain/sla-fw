#!/usr/bin/env python3

import unittest
import logging
from pathlib import Path

from sl1fw.tests.base import Sl1fwTestCase

from sl1fw import defines
from sl1fw import libConfig


class TestScreen(Sl1fwTestCase):
    PROJECT = str(Sl1fwTestCase.SAMPLES_DIR / "numbers.sl1")
    FB_DEV = str(Sl1fwTestCase.TEMP_DIR / "test.fbdev")
    DISPLAY_USAGE = str(Sl1fwTestCase.TEMP_DIR / "display_usage.npz")

    def __init__(self, *args, **kwargs):
        self.hw_config = None
        super().__init__(*args, **kwargs)

    def setUp(self):
        defines.doFBSet = False
        defines.fbFile = self.FB_DEV
        defines.factoryConfigFile = str(self.SL1FW_DIR / ".." / "factory/factory.toml")
        defines.displayUsageData = self.DISPLAY_USAGE

        self.hw_config = libConfig.HwConfig(defines.hwConfigFile)
        from sl1fw.libScreen import Screen
        self.screen = Screen(self.hw_config)
        self.screen.start()

    def tearDown(self):
        self.screen.exit()
        fbdev_path = Path(TestScreen.FB_DEV)
        if fbdev_path.exists():
            fbdev_path.unlink()

    def test_screen(self):
        area_map = {
            2: (2, 1),
            4: (2, 2),
            6: (3, 2),
            8: (4, 2),
            9: (3, 3),
        }

        divide = area_map[9]
        width, height = self.screen.getResolution()

        if width > height:
            x = 0
            y = 1
        else:
            x = 1
            y = 0

        step_w = width // divide[x]
        step_h = height // divide[y]

        calib_areas = list()
        lw = 0
        time = 4.0
        time_step = 1.0
        w = 0
        for i in range(divide[x]):
            lh = 0
            for j in range(divide[y]):
                w = (i + 1) * step_w
                h = (j + 1) * step_h
                logging.debug("%d,%d (%d,%d)", lw, lh, step_w, step_h)
                calib_areas.append(((lw, lh), (step_w, step_h), time))
                time += time_step
                lh = h
            #endfor
            lw = w
        #endfor

        file = "numbers00000.png"

        self.screen.openZip(filename=TestScreen.PROJECT)
        self.screen.createMasks(perPartes=self.hw_config.perPartes)
        self.screen.createCalibrationOverlay(areas=calib_areas, filename=file,
                                             penetration=0.5 / self.hw_config.pixelSize)
        self.screen.preloadImg(filename=file, overlayName='calibPad', whitePixelsThd=50)
        self.screen.blitImg()

        self.screen.saveDisplayUsage()

if __name__ == '__main__':
    unittest.main()
