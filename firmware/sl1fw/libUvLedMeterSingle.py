# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import logging
import serial
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from time import sleep

from sl1fw import defines

class UvLedMeterSingle:

    uvLedMeterDevice = "/dev/uvmeter-single"
    uvSensorType = 1

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.ndigits = 1
        self.port = None
        self.value = None
        self.center = 0
        self.edge = 0
    #enddef


    @property
    def present(self):
        return os.path.exists(self.uvLedMeterDevice)
    #enddef


    @property
    def placementCenter(self):
        return {'x': 40, 'y': 63.5, 'w': 20, 'h': 11.25}
    #enddef


    @property
    def placementCenterConfirm(self):
        return { 'text' : _("TODO: Place the meter to the hole in center") }
    #enddef


    @property
    def placementEdge(self):
        return {'x': 0, 'y': 0, 'w': 20, 'h': 11.25}
    #enddef


    @property
    def placementEdgeConfirm(self):
        return { 'text' : _("TODO: Place the meter to the hole on odge") }
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

            self.port.write(('@\n').encode())
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
            while reply is None or not reply.startswith("<connected analog"):
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


    def read(self, fast = False):
        self.value = None

        try:
            command = ">get%s\n" % (" it" if fast else "")
            self.logger.debug("UV meter command: %s", command)
            self.port.write(command.encode())
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

            data = [ int(x) for x in line[1:].split(',') ]
        except Exception as e:
            self.logger.exception("Invalid response:")
            return False
        #endtry

        if len(data) != 2:
            self.logger.error("Invalid response - wrong line items")
            return False
        #endtry

        self.temp = data[1] / 10.0
        self.value = data[0] / 10.0
        self.datetime = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        return True
    #enddef


    def getData(self, onCenter, data):
        data.uvSensorType = self.uvSensorType
        if self.value is None:
            data.uvSensorData = None
            data.uvTemperature = None
            data.uvDateTime = None
            data.uvMean = None
            data.uvStdDev = None
            data.uvMinValue = None
            data.uvMaxValue = None
            data.uvPercDiff = None
        else:
            if onCenter:
                self.center = self.value * 0.9  # make value similar to the weighted arithmetic mean from UV meter multi
            else:
                self.edge = self.value
            #endif
            mean = ((self.center + self.edge) / 2)
            if mean > 0:
                percCenter = round((self.center - mean) / (mean / 100), self.ndigits)
                percEdge = round((self.edge - mean) / (mean / 100), self.ndigits)
            else:
                percCenter = 100.0
                percEdge = 100.0
            #endif
            data.uvSensorData = list((round(self.center), round(self.edge)))
            data.uvTemperature = round(self.temp, self.ndigits)
            data.uvDateTime = self.datetime
            data.uvMean = round(self.center, self.ndigits)
            data.uvStdDev = 0.0
            data.uvMinValue = round(min(self.center, self.edge))
            data.uvMaxValue = round(max(self.center, self.edge))
            data.uvPercDiff = list((percCenter, percEdge))
        #endif
        return data
    #enddef


    def checkPlace(self, fillFce, onCenter, data):
        self.read()
        if self.value is None:
            return defines.uvMeterErrorComm
        #endif
        if self.value > 2:
            return defines.uvMeterErrorTrans
        #enddef
        fillFce(area = self.placementCenter if onCenter else self.placementEdge, color = 255)
        sleep(0.5)
        self.read(fast = True)
        if self.value is None:
            return defines.uvMeterErrorComm
        #endif
        if self.value < 3:
            return defines.uvMeterErrorInt
        #endif
    #enddef


    def savePic(self, width, height, text, filename, data):
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
            perc = list((0,0))
        #endif

        image = Image.new('RGB', (width, height))
        font = ImageFont.truetype(fontFile, fontSize)
        metrics = font.getmetrics()
        textSize = metrics[0] + metrics[1]
        fontSmall = ImageFont.truetype(fontFile, fontSmallSize)
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

        color = int(round(63 + stepColor * (values[1] - data['uvMinValue'])))
        surf.rectangle(((0, textSize), (width, height)), (0, 0, color))
        val = str(values[1])
        rect = font.getsize(val)
        ofsetX = int((width - rect[0]) / 2)
        ofsetY = height - 2 * textSize
        surf.text((ofsetX, ofsetY), val, fill = textColor, font = font)
        val = "%+.1f %%" % perc[1]
        rect = fontSmall.getsize(val)
        ofsetX = int((width - rect[0]) / 2)
        surf.text((ofsetX, ofsetY + textSize), val, fill = percMinusColor if perc[1] < 0 else percPlusColor, font = fontSmall)

        color = int(round(63 + stepColor * (values[0] - data['uvMinValue'])))
        surf.rectangle(((width / 8, height / 4), (width * 7 / 8, textSize + height * 3 / 4)), (0, 0, color))
        val = str(values[0])
        rect = font.getsize(val)
        ofsetX = int((width - rect[0]) / 2)
        ofsetY = height / 2
        surf.text((ofsetX, ofsetY), val, fill = textColor, font = font)
        val = "%+.1f %%" % perc[0]
        rect = fontSmall.getsize(val)
        ofsetX = int((width - rect[0]) / 2)
        surf.text((ofsetX, ofsetY + textSize), val, fill = percMinusColor if perc[0] < 0 else percPlusColor, font = fontSmall)

        image.save(filename)
    #enddef

#endclass
