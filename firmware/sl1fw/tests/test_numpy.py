#!/usr/bin/env python2

import unittest
from time import sleep
import pygame
import numpy as np
import os


class TestNumpy(unittest.TestCase):
    ZABA = os.path.join(os.path.dirname(__file__), "../../../zaba.png")

    def setUp(self):
        os.environ['SDL_NOMOUSE'] = '1'
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
        pygame.display.init()

        self.screen = pygame.display.set_mode((1440, 2560), pygame.FULLSCREEN, 32)
        self.screen.set_alpha(None)

    def test_numpy(self):
        obr = pygame.image.load(TestNumpy.ZABA).convert()
        obrRect = obr.get_rect()
        self.screen.blit(obr, obrRect)
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