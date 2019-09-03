#!/usr/bin/env python3

import unittest
from pathlib import Path
import pygame
import numpy as np
import os

import sl1fw


class TestNumpy(unittest.TestCase):
    ZABA = str(Path(sl1fw.__file__).parent / ".." / ".." / "zaba.png")

    def __init__(self, *args, **kwargs):
        self.screen = None
        super().__init__(*args, **kwargs)

    def setUp(self):
        os.environ['SDL_NOMOUSE'] = '1'
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
        pygame.display.init()

        self.screen = pygame.display.set_mode((1440, 2560), pygame.FULLSCREEN, 32)
        self.screen.set_alpha(None)

    def test_numpy(self):
        obr = pygame.image.load(TestNumpy.ZABA).convert()
        obr_rect = obr.get_rect()
        self.screen.blit(obr, obr_rect)
        pygame.display.flip()

        pixels = pygame.surfarray.pixels3d(self.screen)

        self.assertEqual(pixels.size, 11059200, "Test pixel count")
        self.assertEqual(np.amin(pixels), 0, "Test min pixel value")
        self.assertEqual(np.amax(pixels), 255, "Test max pixel value")

        hist = np.histogram(pixels, [0, 51, 102, 153, 204, 255])
        self.assertEqual(hist[1].tolist(), [0, 51, 102, 153, 204, 255], "Test histogram[1] match")
        self.assertEqual(hist[0].tolist(), [9440892, 10119, 21582, 9873, 1576734], "Test histogram[0] match")

        pixels ^= 2 ** 32 - 1
        del pixels

        pygame.display.flip()


if __name__ == '__main__':
    unittest.main()
