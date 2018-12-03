#!/usr/bin/env python2

from time import sleep
import pygame
import numpy as np

pygame.display.init()

screen = pygame.display.set_mode((0,0), pygame.FULLSCREEN)
screen.set_alpha(None)

obr = pygame.image.load("test.png").convert()
obrRect = obr.get_rect()
screen.blit(obr, obrRect)
#pygame.display.flip()

pixels = pygame.surfarray.pixels3d(screen)
print pixels.size
print np.amin(pixels)
print np.amax(pixels)
hist = np.histogram(pixels, [0, 51, 102, 153, 204, 255])
print hist[1]
print hist[0]

#pixels ^= 2 ** 32 - 1

del pixels

#sleep(1)
 
#pygame.display.flip()

#sleep(1)
