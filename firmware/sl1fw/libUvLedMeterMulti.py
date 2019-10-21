# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import logging
import serial
import numpy
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from time import sleep

from sl1fw import defines

class UvLedMeterMulti:

    uvLedMeterDevice = "/dev/uvmeter"
    uvSensorType = 0
    INTENSITY_ERROR_THRESHOLD = 0.5

    WEIGHTS = numpy.array([ \
            0.30, 0.30, 0.30, 0.30, 0.30, 0.30, 0.30, 0.30, 0.30, 0.30, \
            0.30, 0.75, 0.75, 0.75, 0.75, 0.75, 0.75, 0.75, 0.75, 0.30, \
            0.30, 0.75, 1.30, 1.30, 1.30, 1.30, 1.30, 1.30, 0.75, 0.30, \
            0.30, 0.75, 1.30, 1.30, 1.30, 1.30, 1.30, 1.30, 0.75, 0.30, \
            0.30, 0.75, 0.75, 0.75, 0.75, 0.75, 0.75, 0.75, 0.75, 0.30, \
            0.30, 0.30, 0.30, 0.30, 0.30, 0.30, 0.30, 0.30, 0.30, 0.30, \
            ])

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.ndigits = 1
        self.port = None
        self.np = None
    #enddef


    @property
    def present(self):
        return os.path.exists(self.uvLedMeterDevice)
    #enddef


    @property
    def placementCenter(self):
        return {'x': 0, 'y': 0, 'w': 100, 'h': 100}
    #enddef


    @property
    def placementCenterConfirm(self):
        return None
    #enddef


    @property
    def placementEdge(self):
        return {'x': 0, 'y': 0, 'w': 100, 'h': 100}
    #enddef


    @property
    def placementEdgeConfirm(self):
        return None
    #enddef


    def connect(self):
        try:
            self.port = serial.Serial(port = self.uvLedMeterDevice,
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
        if self.port is not None:
            self.port.close()
        #endif
        self.port = None
    #enddef


    def read(self):
        sleep(3)
        self.np = None
        try:
            self.port.write(('>all\n').encode())
            self.logger.debug("UV meter command reply: %s", self.port.readline().strip().decode())
            timeout = defines.uvLedMeterMaxWait_s * 10
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


    def getData(self, onCenter, data):
        data.uvSensorType = self.uvSensorType
        if self.np is None:
            data.uvSensorData = None
            data.uvTemperature = None
            data.uvDateTime = None
            data.uvMean = None
            data.uvStdDev = None
            data.uvMinValue = None
            data.uvMaxValue = None
            data.uvPercDiff = None
        else:
            # float and int type conversions from numpy data types are required for toml save algorithm
            mean = numpy.average(self.np, weights = self.WEIGHTS)
            data.uvSensorData = self.np.tolist()
            data.uvTemperature = round(self.temp, self.ndigits)
            data.uvDateTime = self.datetime
            data.uvMean = float(round(mean, self.ndigits))
            data.uvStdDev = float(round(self.np.std(), self.ndigits))
            data.uvMinValue = int(self.np.min())
            data.uvMaxValue = int(self.np.max())
            data.uvPercDiff = ((self.np - mean) / (mean / 100.0)).round(self.ndigits).tolist() if mean > 0 else list()
        #endif
        return data
    #enddef


    def checkPlace(self, fillFce, onCenter, data):
        self.read()
        if self.np is None:
            return defines.uvMeterErrorComm
        #enddef
        data = self.getData(onCenter, data)
        if data.uvMean > 1.0 or data.uvMaxValue > 2:
            return defines.uvMeterErrorTrans
        #enddef
        fillFce(area = self.placementCenter if onCenter else self.placementEdge, color = 255)
        self.read()
        if self.np is None:
            return defines.uvMeterErrorComm
        #endif
        if self.np.min() < 3:
            return defines.uvMeterErrorInt
        #endif
    #enddef


    def savePic(self, width, height, text, filename, data):
        cols = 10
        rows = 6
        bgColor = (0, 0, 0)
        textColor = (255, 255, 255)
        percPlusColor = (0, 255, 0)
        percMinusColor = (255, 0, 0)
        fontFile = os.path.join(defines.dataPath, "FreeSansBold.otf")
        fontSize = height // 15
        fontSmallSize = height // 30

        values = data.get('uvSensorData', None)
        if values is None:
            self.logger.warning("No data to show")
            return False
        #endif
        perc = data['uvPercDiff']
        if not perc:
            perc = 60 * list((0,))
        #endif

        image = Image.new('RGB', (width, height))
        font = ImageFont.truetype(fontFile, fontSize)
        metrics = font.getmetrics()
        textSize = metrics[0] + metrics[1]
        fontSmall = ImageFont.truetype(fontFile, fontSmallSize)
        stepX = int(width / cols)
        stepY = int((height - textSize) / rows)
        valDiff = data['uvMaxValue'] - data['uvMinValue']
        if valDiff:
            stepColor = 192.0 / valDiff
        else:
            stepColor = 0
        #endif
        surf = ImageDraw.Draw(image)

        surf.rectangle(((0, 0), (width, textSize)), bgColor)
        status = "ø %.1f   σ %.1f   %.1f °C   %s" % (
                data['uvMean'],
                data['uvStdDev'],
                data['uvTemperature'],
                data['uvDateTime'])
        rect = font.getsize(status)
        surf.text((width - rect[0], 0), status, fill = textColor, font = font)
        surf.text((0, 0), text, fill = textColor, font = font)

        for col in range(cols):
            for row in range(rows):
                i = col + 10 * row
                color = int(round(63 + stepColor * (values[i] - data['uvMinValue'])))
                posX = col * stepX
                posY = textSize + (row * stepY)
                surf.rectangle(((posX, posY), (posX + stepX, posY + stepY)), (0, 0, color))

                val = str(values[i])
                rect = font.getsize(val)
                ofsetX = int((stepX - rect[0]) / 2)
                ofsetY = int((stepY - rect[1]) / 2)
                surf.text((posX + ofsetX, posY + ofsetY), val, fill = textColor, font = font)

                val = "%+.1f %%" % perc[i]
                rect = fontSmall.getsize(val)
                ofsetX = int((stepX - rect[0]) / 2)
                surf.text((posX + ofsetX, posY + ofsetY + textSize), val, fill = percMinusColor if perc[i] < 0 else percPlusColor, font = fontSmall)
            #endfor
        #endfor
        image.save(filename)
    #enddef

#endclass
