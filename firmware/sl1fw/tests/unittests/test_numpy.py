#!/usr/bin/env python3

import unittest
from pathlib import Path
from PIL import Image
import numpy as np
import os

from sl1fw.tests.base import Sl1fwTestCase

from sl1fw import defines


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
