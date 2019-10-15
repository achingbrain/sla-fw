#!/usr/bin/env python3

# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from PIL import Image
import numpy as np

from sl1fw.tests.base import Sl1fwTestCase


class TestNumpy(unittest.TestCase):
    ZABA = Sl1fwTestCase.SAMPLES_DIR / "zaba.png"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def test_numpy(self):
        obr = Image.open(TestNumpy.ZABA)
#        obr.show()
        self.assertEqual(obr.mode, "L", "Image mode match")
        pixels = np.array(obr)

        self.assertEqual(pixels.size, 3686400, "Test pixel count")
        self.assertEqual(np.amin(pixels), 0, "Test min pixel value")
        self.assertEqual(np.amax(pixels), 255, "Test max pixel value")

        hist = np.histogram(pixels, [0, 51, 102, 153, 204, 255])
        self.assertEqual(hist[1].tolist(), [0, 51, 102, 153, 204, 255], "Test histogram[1] match")
        self.assertEqual(hist[0].tolist(), [3146964, 3373, 7194, 3291, 525578], "Test histogram[0] match")


if __name__ == '__main__':
    unittest.main()
