# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018 Prusa Research s.r.o. - www.prusa3d.com

import os
import logging
import threading, Queue
import serial
from time import sleep

import defines


class NextionRead(threading.Thread):

    def __init__(self, read, events):
        super(NextionRead, self).__init__()
        self.logger = logging.getLogger(__name__)
        self.read = read
        self.events = events
        self.stoprequest = threading.Event()
    #enddef


    def run(self):
        #self.logger.debug("thread started")
        while not self.stoprequest.isSet():
            message = self.read()
            if message[0] == "TE":  # Touch Event only
                if self.events.empty():
                    self.events.put(message[1:])
                else:
                    self.logger.warning("Last event was not red, ignoring new one")
                #endif
            #endif
            sleep(0.1)
        #endwhile
        #self.logger.debug("thread ended")
    #enddef


    def join(self, timeout = None):
        self.stoprequest.set()
        super(NextionRead, self).join(timeout)
    #enddef

#endclass


class NextionDisplay(object):

    def __init__(self, hwConfig, hw):
        self.type = "Nextion Display"

        self.model = "NX4827T043_011R"
        self.lockFile = "/run/serial_in_use"
        self.defaultBaudrate = 9600
        self.baudrate = 115200
        self.firmwareVersion = 206

        self.logger = logging.getLogger(__name__)
        self.hwConfig = hwConfig
        self.hw = hw
        self.actualPage = 0
        self.netActive = False

        self.pageMap = {
                "intro"         : 0, # intro
                "start"         : 1, # start
                "home"          : 2, # home
                "control"       : 3, # control
                "wait"          : 4, # wait
                "settings"      : 5, # settings
                "confirm"       : 6, # confirm
                "print"         : 7, # print
                "homeprint"     : 8, # homeprint
                "projsettings"  : 9, # projsettings
                "change"        : 10, # change
                "sysinfo"       : 11, # systeminfo
                "netinfo"       : 12, # netinfo
                "about"         : 13, # about
                "sourceselect"  : 14, # usblan
                "error"         : 15, # error
                "towermove"     : 16, # towermove
                "tiltmove"      : 17, # tiltmove
                "exception"     : 18, # exception
                "admin"         : 19, # admin
                "setup"         : 20, # setup
                }
        self.itemMap = {
                0 : { # intro
                    },
                1 : { # start
                    "progress"  : (1, True),    # self.bootProgress()!!!
                    },
                2 : { # home
                    "wifi"      : (1, False),
                    "info"      : (2, False),
                    "control"   : (3, False),
                    "settings"  : (4, False),
                    "print"     : (5, False),
                    "turnoff"   : (6, False),
                    },
                3 : { # control
                    "wifi"      : (1, False),
                    "info"      : (2, False),
                    "top"       : (3, False),
                    "tankres"   : (4, False),
                    "up"        : (5, False),
                    "back"      : (6, False),
                    },
                4 : { # wait
                    "line1"     : (2, True),
                    "line2"     : (3, True),
                    "line3"     : (4, True),
                    },
                5 : { # settings
                    "wifi"      : (1, False),
                    "info"      : (2, False),
                    "projsett"  : (3, False),
                    "sysinfo"   : (4, False),
                    "change"    : (5, False),
                    "back"      : (6, False),
                    },
                6 : { # confirm
                    "line1"     : (1, True),
                    "line2"     : (2, True),
                    "line3"     : (3, True),
                    "cont"      : (4, False),
                    "back"      : (5, False),
                    },
                7 : { # print
                    "wifi"      : (1, False),
                    "info"      : (2, False),
                    "percent"   : (3, True),
                    "timeelaps" : (4, True),
                    "progress"  : (5, True),
                    "timeremain": (6, True),
                    "line1"     : (7, True),
                    "line2"     : (8, True),
                    "line3"     : (9, True),
                    "line4"     : (10, True),
                    "setup"     : (11, False),
                    },
                8 : { # homeprint
                    "wifi"      : (1, False),
                    "info"      : (2, False),
                    "updown"    : (3, False),
                    "settings"  : (4, False),
                    "upoff"     : (5, False),
                    "back"      : (6, False),
                    },
                9 : { # projsettings
                    "wifi"      : (1, False),
                    "info"      : (2, False),
                    "line1"     : (3, True),
                    "line2"     : (4, True),
                    "line3"     : (5, True),
                    "change"    : (6, False),
                    "back"      : (7, False),
                    },
                10 : { # change
                    "addsecond" : (1, False),
                    "timeexpos" : (3, True),
                    "subsecond" : (4, False),
                    "back"      : (5, False),
                    },
                11 : { # systeminfo
                    "back"      : (1, False),
                    "wifi"      : (2, False),
                    "info"      : (3, False),
                    "line1"     : (4, True),
                    "line2"     : (5, True),
                    "line3"     : (6, True),
                    "line4"     : (7, True),
                    "line5"     : (8, True),
                    "line6"     : (9, True),
                    "line7"     : (10, True),
                    "line8"     : (11, True),
                    "line9"     : (12, True),
                    "line10"    : (13, True),
                    },
                12 : { # netinfo
                    "back"      : (1, False),
                    "line1"     : (2, True),
                    "line2"     : (3, True),
                    "qr1"       : (4, True),
                    "qr2"       : (5, True),
                    "qr1label"  : (6, True),
                    "qr2label"  : (7, True),
                    },
                13 : { # about
                    "back"      : (1, False),
                    "line1"     : (2, True),
                    "line2"     : (3, True),
                    "qr1"       : (4, True),
                    "admin"     : (5, False),
                    },
                14 : { # usblan
                    "back"      : (1, False),
                    "wifi"      : (2, False),
                    "info"      : (3, False),
                    "line1"     : (4, True),
                    "line2"     : (5, True),
                    "line3"     : (6, True),
                    "usb"       : (7, False),
                    "lan"       : (8, False),
                    },
                15 : { # error
                    "line1"     : (1, True),
                    "line2"     : (2, True),
                    "line3"     : (3, True),
                    "back"      : (4, False),
                    "turnoff"   : (5, False),
                    },
                16 : { # towermove
                    "upfast"    : (1, False),
                    "upslow"    : (2, False),
                    "value"     : (4, True),
                    "downfast"  : (5, False),
                    "downslow"  : (6, False),
                    "back"      : (7, False),
                    },
                17 : { # tiltmove
                    "upfast"    : (1, False),
                    "upslow"    : (2, False),
                    "value"     : (4, True),
                    "downfast"  : (5, False),
                    "downslow"  : (6, False),
                    "back"      : (7, False),
                    },
                18 : { # exception
                    "line1"     : (2, True),
                    "line2"     : (3, True),
                    "line3"     : (4, True),
                    "qr1"       : (5, True),
                    },
                19 : { # admin
                    "button1"   : (1, True),
                    "button2"   : (2, True),
                    "button3"   : (3, True),
                    "button4"   : (4, True),
                    "button5"   : (5, True),
                    "button6"   : (6, True),
                    "button7"   : (7, True),
                    "button8"   : (8, True),
                    "button9"   : (9, True),
                    "button10"  : (10, True),
                    "button11"  : (11, True),
                    "button12"  : (12, True),
                    "button13"  : (13, True),
                    "button14"  : (14, True),
                    "back"      : (15, True),
                    },
                20 : { # setup
                    "label1g1"  : (1, True),
                    "label1g2"  : (2, True),
                    "label1g3"  : (3, True),
                    "label1g4"  : (4, True),
                    "label1g5"  : (5, True),
                    "label1g6"  : (6, True),
                    "label1g7"  : (7, True),
                    "label1g8"  : (8, True),
                    "state1g1"  : (9, True),
                    "state1g2"  : (10, True),
                    "state1g3"  : (11, True),
                    "state1g4"  : (12, True),
                    "state1g5"  : (13, True),
                    "state1g6"  : (14, True),
                    "state1g7"  : (15, True),
                    "state1g8"  : (16, True),
                    "label2g1"  : (17, True),
                    "label2g2"  : (18, True),
                    "label2g3"  : (19, True),
                    "label2g4"  : (20, True),
                    "label2g5"  : (21, True),
                    "label2g6"  : (22, True),
                    "label2g7"  : (23, True),
                    "label2g8"  : (24, True),
                    "minus2g1"  : (25, False),
                    "minus2g2"  : (26, False),
                    "minus2g3"  : (27, False),
                    "minus2g4"  : (28, False),
                    "minus2g5"  : (29, False),
                    "minus2g6"  : (30, False),
                    "minus2g7"  : (31, False),
                    "minus2g8"  : (32, False),
                    "value2g1"  : (33, True),
                    "value2g2"  : (34, True),
                    "value2g3"  : (35, True),
                    "value2g4"  : (36, True),
                    "value2g5"  : (37, True),
                    "value2g6"  : (38, True),
                    "value2g7"  : (39, True),
                    "value2g8"  : (40, True),
                    "plus2g1"   : (41, False),
                    "plus2g2"   : (42, False),
                    "plus2g3"   : (43, False),
                    "plus2g4"   : (44, False),
                    "plus2g5"   : (45, False),
                    "plus2g6"   : (46, False),
                    "plus2g7"   : (47, False),
                    "plus2g8"   : (48, False),
                    "button1"   : (49, True),
                    "button2"   : (50, True),
                    "button3"   : (51, True),
                    "button4"   : (52, True),
                    "back"      : (53, True),
                    },
                }

        self.pageIDmap = dict(zip(self.pageMap.values(), self.pageMap.keys()))
        self.itemIDmap = {}
        for pageId in self.pageIDmap.keys():
            for key, val in self.itemMap[pageId].iteritems():
                self.itemIDmap[(pageId, val[0])] = key
            #endfor
        #endfor

        # pokud jeste bezi plymouth, pockame
        if os.path.isfile(self.lockFile):
            self.logger.info("Waiting for serial port...")
            while os.path.isfile(self.lockFile):
                sleep(0.1)
            #endwhile
            self.logger.info("Serial port is ready")
        #endif

        # rychlost a timeouty meni nasledny displayInit()!!!
        self.port = serial.Serial(port = defines.nextionDevice,
                baudrate = self.defaultBaudrate,
                bytesize = 8,
                parity = 'N',
                stopbits = 1,
                timeout = 1.0,
                writeTimeout = 1.0,
                xonxoff = False,
                rtscts = False,
                dsrdtr = False,
                interCharTimeout = None)

        self._displayInit()
        self._firmwareCheck()

        self.nextionEvents = Queue.Queue()
        self.nextionRead = NextionRead(self._read, self.nextionEvents)
        self.nextionRead.start()

        self.neXcmd("page start")
    #enddef


    def bootProgress(self, percent):
        self.neXval(1, percent)
    #endef


    def __del__(self):
        self.stop()
    #enddef


    def _displayInit(self):
        connected = False
        # TODO neopakovat do nekonecna?
        while not connected:
            for baudrate in (self.defaultBaudrate, self.baudrate):
                self.port.baudrate = baudrate
                self.port.timeout = 3000/baudrate + 0.3
                self.port.flushInput()
                self.logger.debug('Trying connect to nextion display at %s bd', baudrate)
                self.port.write("\xff\xff\xff")
                self.port.write('connect')
                self.port.write("\xff\xff\xff")
                r = self.port.read(128)
                if 'comok' in r:
                    connected = True
                    self.logger.info('Nextion display connected at %d bd', baudrate)
                    status, unknown1, model, unknown2, version, serial, flash_size = r.strip("\xff\x00").split(',')
                    self.logger.debug('Status: %s', status)
                    self.logger.debug('Model: %s', model)
                    self.logger.debug('Version: %s', version)
                    self.logger.debug('Serial: %s', serial)
                    self.logger.debug('Flash size: %s', flash_size)
                    if model != self.model:
                        self.logger.warning("Display model (%s) does not match driver model (%s)", model, self.model)
                    #endif
                    break
                #endif
            #endfor
            if not connected:
                self.hw.beepAlarm(5)
            #endif
        #endwhile

        if connected:
            self.logger.debug('Setting %d bd', self.baudrate)
            self.neXcmd("bauds=%d" % self.baudrate)
            sleep(0.05)
            self.port.baudrate = self.baudrate
            self.port.timeout = 3000 / self.baudrate + 0.3
            self.port.writeTimeout = 3000 / self.baudrate + 0.3
        #endif
    #enddef


    def _firmwareCheck(self):
        self.neXcmd('get intro.version.val')
        while not self.port.inWaiting():
            sleep(0.05)
        #endwhile
        message = self._read()
        if message[0] != "ND" or message[1] != self.firmwareVersion:
            self.logger.warning("Wrong display firmware version, flash forced.")
            self.hw.beepAlarm(4)
            if not self._flashRaw(self.hwConfig.design, self.hwConfig.nextionRotate, "data/"):
                self.logger.error("Forced flash failed!")
                self.hw.beepAlarm(5)
                # FIXME neco s tim udelat?
            #endif
        #endif
    #enddef


    def _read(self):
        try:
            if self.port.inWaiting():
                message = self.port.read(4)
                while len(message) < 4 or message[-3:] != "\xff\xff\xff":
                    message += self.port.read()
                #endwhile

                #self.logger.debug("message: %s", message.encode("hex"))

                # touch event
                if len(message) == 7 and ord(message[0]) == 0x65:
                    pageId = ord(message[1])
                    componentId = ord(message[2])
                    pressed = ord(message[3]) == 1
                    return ("TE", pageId, componentId, pressed)
                #endif

                # string data
                if ord(message[0]) == 0x70:
                    string = message[1:-3]
                    return ("SD", string)
                #endif

                # numeric data
                if ord(message[0]) == 0x71:
                    number = ord(message[1])
                    number += ord(message[2]) * 256
                    number += ord(message[3]) * 65536
                    number += ord(message[4]) * 16777216
                    return ("ND", number)
                #endif

                self.logger.warning("unknown message '%s', ignoring", message.encode("hex"))
            #endif

        except Exception:
            self.logger.exception("read exception:")
        #endtry

        return (None,)
    #enddef


    def hasFirmware(self):
        return True
    #enddef


    def assignNetActive(self, value):
        self.netActive = value
        self._setWiFiIcon(forceOff = True)
    #endif


    def flash(self, design, path):
        self.stop()
        if not self._flashRaw(design, self.hwConfig.nextionRotate, path):
            return False
        #endif
        self.nextionEvents = Queue.Queue()
        self.nextionRead = NextionRead(self._read, self.nextionEvents)
        self.nextionRead.start()
        return True
    #enddef


    def _flashRaw(self, design, rotate, path):
        filename = "%s%s-%s-%s.tft" % (path, self.model, design, "rot" if rotate else "nor")
        try:
            fsize = os.path.getsize(filename)
            self.logger.info('filesize: %d', fsize)
        except Exception:
            self.logger.exception("getsize() exception:")
            return False
        #endtry

        self.port.write("rest\xff\xff\xff")
        self.port.flush()
        self._waitAck('\x88')

        self.port.write('whmi-wri %i,%i,0' % (fsize, self.baudrate))
        self.port.write("\xff\xff\xff")
        self.port.flush()
        self.port.timeout = 0.5
        self.port.writeTimeout = 5.0
        sleep(0.5)
        self.logger.debug('Waiting for ACK')
        self._waitAck('\x05')
        self.logger.info('Uploading')
        percOld = None
        with open(filename, 'rb') as hmif:
            dcount = 0
            while True:
                data = hmif.read(4096)
                if len(data) == 0: break
                dcount += len(data)
                #self.logger.debug('writing %i', len(data))
                self.port.write(data)
                perc = int(100 * dcount / fsize)
                if percOld != perc:
                    self.logger.info("done %d %%", perc)
                    percOld = perc
                #endif
                #self.logger.debug('waiting for hmi')
                self._waitAck('\x05')
            #endwhile
        #endwith
        sleep(5)
        self._displayInit()
        return True
    #enddef


    def _waitAck(self, ack):
        r = ''
        while ack not in r:
            r = self.port.read(1)
            if r != '' and r != ack:
                self.logger.debug('<%r>', r)
            #endif
            sleep(0.1)
        #endwhile
    #enddef


    def _setWiFiIcon(self, forceOff = False):
        # nastaveni obrazku pro WiFi
        wifiId = self.itemMap[self.actualPage].get("wifi", None)
        if wifiId is not None:
            if self.netActive:
                self.neXcmd('id%d.pic=31' % wifiId[0])
                self.neXcmd('id%d.pic2=32' % wifiId[0])
            elif forceOff:
                self.neXcmd('id%d.pic=27' % wifiId[0])
                self.neXcmd('id%d.pic2=28' % wifiId[0])
            #endif
        #endif
    #enddef


    def getEventNoWait(self):
        try:
            pageId, componentId, pressed = self.nextionEvents.get_nowait()
            return { 'page' : self.pageIDmap[pageId], 'id' : self.itemIDmap[(pageId, componentId)], 'pressed' : pressed }
        except Queue.Empty:
            pass
        except Exception:
            self.logger.exception("pageId:%d componentId:%d pressed:%s", pageId, componentId, str(pressed))
        #endtry

        return { 'page' : None, 'id' : None, 'pressed' : None }
    #enddef


    def stop(self):
        self.nextionRead.join()
    #endef


    # pro Nextion zaroven showPage()
    def setPage(self, page):
        self.actualPage = self.pageMap.get(page, None)
        if self.actualPage is None:
            self.logger.error("unknown page '%s'", page)
            return
        #endif

        #self.logger.debug("page '%s' is '%d'", page, self.actualPage)
        self.neXcmd("page %d" % self.actualPage)

        self._setWiFiIcon()
    #enddef


    def showPage(self):
        pass
    #enddef


    # pro Nextion shodna se showItems()
    def setItems(self, items):
        self.showItems(items)
    #enddef


    def showItems(self, items):
        if self.actualPage is None:
            self.logger.error("no actual page is set")
            return
        #endif

        for name, value in items.iteritems():
            itemId, writable = self.itemMap[self.actualPage].get(name, (None, False))
            if itemId is None:
                self.logger.error("on page '%d' is no item '%s'", self.actualPage, name)
                return
            #endif
            if not writable:
                self.logger.error("item '%d.%s' is not writable", self.actualPage, name)
                return
            #endif

            #self.logger.debug("item '%s' is 'id%d'", name, itemId)

            if type(value).__name__ == "str":
                try:
                    newValue = value.decode('utf8').encode('iso-8859-2')
                except Exception:
                    newValue = value
                #endtry
                self.neXtxt(itemId, newValue)
            else:
                self.neXval(itemId, value)
            #endif
        #endfor
    #enddeF


    def neXcmd(self, co):
        #self.logger.debug('%s\xff\xff\xff', co)
        try:
            self.port.write('%s\xff\xff\xff' % co)
        except Exception:
            self.logger.exception("write exception:")
        #endtry
    #enddef


    def neXtxt(self, kam, label):
        #self.logger.debug('id%d.txt="%s"\xff\xff\xff', kam, label)
        try:
            self.port.write('id%d.txt="%s"\xff\xff\xff' % (kam, label))
        except Exception:
            self.logger.exception("write exception:")
        #endtry
    #enddef


    def neXval(self, kam, num):
        #self.logger.debug('id%d.val=%s\xff\xff\xff', kam, str(num))
        try:
            self.port.write('id%d.val=%s\xff\xff\xff' % (kam, num))
        except Exception:
            self.logger.exception("write exception:")
        #endtry
    #enddef

#endclass
