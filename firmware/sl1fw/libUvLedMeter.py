# part of SL1 firmware
# -*- coding: utf-8 -*-
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import os
import logging
import serial
import numpy
import pygame   # TODO replace with PIL.Image
from datetime import datetime
from time import sleep

from sl1fw import defines

class UvLedMeter:

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.ndigits = 1
        self.np = None
    #enddef


    def connect(self):
        try:
            self.port = serial.Serial(port = defines.uvLedMeterDevice,
                    baudrate = 115200,
                    bytesize = 8,
                    parity = 'N',
                    stopbits = 1,
                    timeout = 1.0,
                    writeTimeout = 1.0,
                    xonxoff = False,
                    rtscts = False,
                    dsrdtr = False,
                    interCharTimeout = None)

            self.logger.info("waiting for UV meter response")
            timeout = 100
            while not self.port.inWaiting() and timeout:
                sleep(0.1)
                timeout -= 1
            #endwhile

            if not timeout:
                self.logger.error("Response timeout")
                return False
            #endif

            reply = None
            while reply != "<done":
                reply = self.port.readline().strip().decode()
                self.logger.debug("UV meter response: %s", reply)
            #endwhile

            self.logger.info("UV meter connected successfully")
            return True

        except Exception as e:
            self.logger.exception("Connection failed:")
            return False
        #endtry
    #enddef


    def close(self):
        self.port.close()
        self.port = None
    #enddef


    def read(self):
        self.np = None
        try:
            self.port.write(('>all\n').encode())
            self.logger.debug("UV meter command reply: %s", self.port.readline().strip().decode())
            timeout = 100
            while not self.port.inWaiting() and timeout:
                sleep(0.1)
                timeout -= 1
            #endwhile
            if not timeout:
                self.logger.error("Response timeout")
                return False
            #endif
            line = self.port.readline().strip().decode()
            self.logger.debug("UV meter response: %s", line)

            if line[0] != '<':
                self.logger.error("Invalid response - wrong line format")
                return False
            #endif

            data = list([int(x) for x in line[1:].split(',')])
        except Exception as e:
            self.logger.exception("Invalid response:")
            return False
        #endtry

        if len(data) != 61:
            self.logger.error("Invalid response - wrong line items")
            return False
        #endtry

        self.temp = data[-1] / 10.0
        self.np = numpy.array(data[:-1])
        self.datetime = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        return True
    #enddef


    def getData(self):
        if self.np is None:
            return {'uvSensorData'  : None,
                    'uvTemperature' : None,
                    'uvDateTime'    : None,
                    'uvMean'        : None,
                    'uvStdDev'      : None,
                    'uvMinValue'    : None,
                    'uvMaxValue'    : None,
                    'uvPercDiff'    : None,
                    }
        else:
            mean = self.np.mean()
            return {'uvSensorData'  : self.np.tolist(),
                    'uvTemperature' : round(self.temp, self.ndigits),
                    'uvDateTime'    : self.datetime,
                    'uvMean'        : round(mean, self.ndigits),
                    'uvStdDev'      : round(self.np.std(), self.ndigits),
                    'uvMinValue'    : self.np.min(),
                    'uvMaxValue'    : self.np.max(),
                    'uvPercDiff'    : ((self.np - mean) / (mean / 100.0)).round(self.ndigits).tolist(),
                    }
        #endif
    #enddef


    def savePic(self, width, height, text, filename, data = None):
        cols = 10
        rows = 6
        bgColor = (0, 0, 0)
        textColor = (255, 255, 255)
        percPlusColor = (0, 255, 0)
        percMinusColor = (255, 0, 0)
        fontFile = os.path.join(defines.dataPath, "FreeSansBold.otf")
        fontSize = height // 15
        fontSmallSize = height // 30

        if data is None:
            data = self.getData()
        #endif
        values = data['uvSensorData']
        if values is None:
            self.logger.warning("No data to show")
            return False
        #endif
        perc = data['uvPercDiff']
        if not len(perc):
            perc = 60 * list((0,))
        #endif

        pygame.init()
        surf = pygame.Surface((width, height))
        font = pygame.font.Font(fontFile, fontSize)
        textSize = font.get_linesize()
        fontSmall = pygame.font.Font(fontFile, fontSmallSize)
        stepX = int(width / cols)
        stepY = int((height - textSize) / rows)
        valDiff = data['uvMaxValue'] - data['uvMinValue']
        if valDiff:
            stepColor = 192.0 / valDiff
        else:
            stepColor = 0
        #endif

        surf.fill(bgColor, ((0, 0), (width, textSize)))

        status = "ø %.1f   σ %.1f   %.1f °C   %s" % (
                data['uvMean'],
                data['uvStdDev'],
                data['uvTemperature'],
                data['uvDateTime'])
        textSurf = font.render(status, True, textColor, bgColor)
        rect = textSurf.get_rect()
        surf.blit(textSurf, (width - rect.w, 0))

        textSurf = font.render(text, True, textColor, bgColor)
        surf.blit(textSurf, (0, 0))

        for col in range(cols):
            for row in range(rows):
                i = col + 10 * row
                color = int(round(63 + stepColor * (values[i] - data['uvMinValue'])))

                posX = col * stepX
                posY = textSize + (row * stepY)
                surf.fill((0, 0, color), ((posX, posY), (stepX, stepY)))

                textSurf = font.render(str(values[i]), True, textColor, color)
                rect = textSurf.get_rect()
                ofsetX = int((stepX - rect.w) / 2)
                ofsetY = int((stepY - rect.h) / 2)
                surf.blit(textSurf, (posX + ofsetX, posY + ofsetY))

                textSurf = fontSmall.render("%+.1f %%" % perc[i], True, percMinusColor if perc[i] < 0 else percPlusColor, color)
                rect = textSurf.get_rect()
                ofsetX = int((stepX - rect.w) / 2)
                surf.blit(textSurf, (posX + ofsetX, posY + ofsetY + textSize))
            #endfor
        #endfor
        pygame.image.save(surf, filename)
        pygame.quit()
    #enddef

#endclass
