# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import logging
from enum import Enum
from typing import Optional
import serial
import re
from time import sleep
from multiprocessing import Lock
import bitstring
from math import ceil
import pydbus
import os
from collections import deque

from sl1fw.libDebug import Debug
from sl1fw import defines


class MotionControllerTracingSerial(serial.Serial):
    """
    This is an extension of Serial that supports logging of traces and reading of decode text lines.
    """
    TRACE_LINES = 30

    class LineMarker(Enum):
        INPUT = ">"
        GARBAGE = "|"
        OUTPUT = "<"
    #endclass

    class LineTrace:
        def __init__(self, marker, line: bytes):
            self._line = line
            self._marker = marker
            self._repeats = 1
        #enddef

        def __eq__(self, other):
            if not isinstance(other, self.__class__):
                return False
            else:
                return self._line == other._line and self._marker == other._marker
            #endif
        #enddef

        def repeat(self):
            self._repeats += 1
        #enddef

        def __str__(self):
            if self._repeats > 1:
                return f"{self._repeats}x {self._marker.value} {self._line}"
            else:
                return f"{self._marker.value} {self._line}"
            #endif
        #enddef
    #endclass

    def __init__(self, *args, **kwargs):
        self.__trace = deque(maxlen=self.TRACE_LINES)
        self.__debug = kwargs['debug']
        del kwargs['debug']
        super().__init__(*args, **kwargs)

    def __append_trace(self, current_trace):
        # < b'?mot\n' -3
        # > b'1 ok\n' -2
        # < b'?mot\n' -1
        # > b'1 ok\n' current_trace

        if len(self.__trace) > 3 and \
                self.__trace[-3] == self.__trace[-1] and \
                self.__trace[-2] == current_trace:
            self.__trace[-3].repeat()
            self.__trace[-2].repeat()
            del self.__trace[-1]
        else:
            self.__trace.append(current_trace)
        #endif
    #enddef

    def readline(self, garbage=False) -> bytes:
        """
        Read raw line from motion controller
        :param garbage: Whenever to mark line read as garbage in command trace
        :return: Line read as raw bytes
        """
        marker = self.LineMarker.GARBAGE if garbage else self.LineMarker.INPUT
        ret = super().readline()
        trace = self.LineTrace(marker, ret)
        self.__append_trace(trace)
        self.__debug.log(str(trace))
        return ret
    #enddef

    def write(self, data: bytes) -> int:
        """
        Write data to a motion controller
        :param data: Data to be written
        :return: Number of bytes written
        """
        self.__append_trace(self.LineTrace(self.LineMarker.OUTPUT, data))
        self.__debug.log(f"< {data}")
        return super().write(data)
    #enddef

    @property
    def trace(self) -> str:
        """
        Get formated motion controller command trace
        :return: Trace string
        """
        return f"last {self.TRACE_LINES} lines:\n" + "\n".join([str(x) for x in self.__trace])
    #enddef

    def read_text_line(self, garbage=False) -> str:
        """
        Read line from serial as stripped decoded text
        :param garbage: Mark this data as garbage. LIne will be amrked as such in trace
        :return: Line read from motion controller
        """
        return self.readline(garbage=garbage).decode("ascii").strip()
    #enddef
#endclass


class MotionControllerException(Exception):
    def __init__(self, message: str, serial: MotionControllerTracingSerial):
        self.__serial = serial
        super().__init__(f"{message}, trace: {serial.trace}")
    #enddef
#endclass


class MotConCom(object):
    MCFWversion = ""
    MCFWrevision = -1
    MCBoardRevision = (-1, -1)
    MCserial = ""

    commOKStr = re.compile('^(.*)ok$')
    commErrStr = re.compile('^e(.)$')
    commErrors = {
            '1' : "unspecified failure",
            '2' : "busy",
            '3' : "syntax error",
            '4' : "parameter out of range",
            '5' : "operation not permitted",
            '6' : "null pointer",
            '7' : "command not found",
            }

    _statusBits = {
            'tower'  :  0,
            'tilt'   :  1,
            'button' :  6,
            'cover'  :  7,
            'endstop':  8,
            'reset'  : 13,
            'fans'   : 14,
            'fatal'  : 15,
            }

    selfCheckErrors = {
            1 : _("Application flash checksum has failed"),
            2 : _("Bootloader flash checksum has failed"),
            3 : _("Serial number check has failed"),
            4 : _("Fuse bit settings have failed"),
            5 : _("Boot-section lock has failed"),
            6 : _("GPIO SPI has failed"),
            7 : _("TMC SPI has failed"),
            8 : _("TMC wiring/communication has failed"),
            9 : _("The UV LED has failed"),
            }

    resetFlags = {
            0 : "power-on",
            1 : "external",
            2 : "brown-out",
            3 : "watchdog",
            4 : "jtag",
            7 : "stack overflow",
            }


    def __init__(self, instance_name):
        self.portLock = Lock()
        self.debug = Debug()
        self.port_trace = deque(maxlen=10)

        self.port = MotionControllerTracingSerial(debug=self.debug)
        self.port.port = defines.motionControlDevice
        self.port.baudrate = 115200
        self.port.bytesize = 8
        self.port.parity = 'N'
        self.port.stopbits = 1
        self.port.timeout = 1.0
        self.port.writeTimeout = 1.0
        self.port.xonxoff = False
        self.port.rtscts = False
        self.port.dsrdtr = False
        self.port.interCharTimeout = None

        super(MotConCom, self).__init__()
        self.logger = logging.getLogger(instance_name)
    #enddef


    def start(self):
        self.port.open()
    #enddef


    def __del__(self):
        self.exit()
    #enddef


    def exit(self):
        self.debug.exit()
        if self.port.is_open:
            self.port.close()
        #endif
    #enddef


    def connect(self, MCversionCheck):
        state = self.getStateBits(('fatal', 'reset'))
        if not state:
            return _("Communication with the motion controller has failed")
        #endif

        if state['fatal']:
            errorCode = self.doGetInt("?err")
            error = self.selfCheckErrors.get(errorCode, _("An unknown issue has occured"))
            return error
        #endif

        if state['reset']:
            resetBits = self.doGetBoolList("?rst", bitCount = 8)
            bit = 0
            for val in resetBits:
                if val:
                    self.logger.info("motion controller reset flag: %s", self.resetFlags.get(bit, "unknown"))
                #endif
                bit += 1
            #endfor
        #endif

        self.MCFWversion = self.do("?ver")
        if MCversionCheck and self.MCFWversion != defines.reqMcVersion:
            return _("Wrong motion controller firmware version")
        else:
            self.logger.info("motion controller firmware version: %s", self.MCFWversion)
        #endif

        tmp = self.doGetIntList("?rev")
        if len(tmp) == 2 and 0 <= divmod(tmp[1], 32)[0] <= 7:
            self.MCFWrevision = tmp[0]
            self.logger.info("motion controller firmware for board revision: %s", self.MCFWrevision)

            self.MCBoardRevision = divmod(tmp[1], 32)
            self.logger.info("motion controller board revision: %d%s", self.MCBoardRevision[1], chr(self.MCBoardRevision[0] + ord('a')))
        else:
            self.logger.warning("invalid motion controller firmware/board revision: %s", str(tmp))
            self.MCFWrevision = -1
            self.MCBoardRevision = (-1, -1)
        #endif

        if self.MCFWrevision != self.MCBoardRevision[1]:
            self.logger.warning("motion controller firmware for board revision (%d) not"
                    " match motion controller board revision (%d)!",
                    self.MCFWrevision, self.MCBoardRevision[1])
        #enddef

        self.MCserial = self.do("?ser")
        if self.MCserial:
            self.logger.info("motion controller serial number: %s", self.MCserial)
        else:
            self.logger.warning("motion controller serial number is invalid")
            self.MCserial = "*INVALID*"
        #endif

        return None
    #enddef


    def doGetInt(self, *args):
        return self.do(*args, return_process=int)
    #enddef


    def doGetIntList(self, cmd, args = (), base = 10, multiply: float = 1):
        return self.do(cmd, *args, return_process=lambda ret: list([int(x, base) * multiply for x in ret.split(" ")]))
    #enddef


    def doGetBool(self, cmd, *args):
        return self.do(cmd, *args, return_process=lambda x: x == "1")
    #enddef


    def doGetBoolList(self, cmd, bitCount, args = ()):
        def process(data):
            bits = list()
            num = int(data)
            for i in range(bitCount):
                bits.append(True if num & (1 << i) else False)
            #endfor
            return bits
        #enddef
        return self.do(cmd, *args, return_process=process)
    #enddef


    def doGetHexedString(self, *args):
        return self.do(*args, return_process=lambda x: bytes.fromhex(x).decode('ascii'))
    #enddef


    def doSetBoolList(self, command, bits):
        bit = 0
        out = 0
        for val in bits:
            out |= 1 << bit if val else 0
            bit += 1
        #endfor
        self.do(command, out)
    #enddef


    def do(self, cmd, *args, return_process=lambda x: x):
        with self.portLock:
            # Read garbage already pending to be read
            # TODO: This is not correct, there should be no random garbage around
            while self.port.inWaiting():
                try:
                    line = self.port.read_text_line(garbage=True)
                    self.logger.debug(f"Garbage pending in MC port: {line}")
                except (serial.SerialException, UnicodeError) as e:
                    raise MotionControllerException(f"Failed garbage read", self.port) from e
                #endtry
            #endwhile

            # Write command
            cmd_string = ' '.join(str(x) for x in (cmd,) + args)
            try:
                self.port.write(f"{cmd_string}\n".encode('ascii'))
            except serial.SerialTimeoutException as e:
                raise MotionControllerException(f"Timeout writing serial port", self.port) from e
            #endtry

            # Read until some response is received
            while True:
                line = self.port.read_text_line()

                ok_match = self.commOKStr.match(line)

                if ok_match is not None:
                    response = ok_match.group(1).strip() if ok_match.group(1) else ""
                    try:
                        return return_process(response)
                    except Exception as e:
                        raise MotionControllerException("Failed to process MC response", self.port) from e
                    #endtry
                #endif

                err_match = self.commErrStr.match(line)
                if err_match is not None:
                    err = self.commErrors.get(err_match.group(1), "unknown error")
                    self.logger.error("error: '%s'", err)
                    raise MotionControllerException(f"MC command failed with error: {err}", self.port)
                else:
                    if line.startswith("#"):
                        self.logger.debug(f"Garbage response received: {line}")
                    else:
                        raise MotionControllerException(f"MC command resulted in non-response line", self.port)
                    #endif
                #endif
            #endwhile
        #endwith
    #enddef


    def flash(self, MCBoardVersion):
        import subprocess

        self.portLock.acquire()
        self.reset()

        process = subprocess.Popen([defines.flashMcCommand, defines.dataPath, str(MCBoardVersion), defines.motionControlDevice], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        while True:
            line = process.stdout.readline()
            retc = process.poll()
            if line == '' and retc is not None:
                break
            #endif
            if line:
                line = line.strip()
                if line == "":
                    continue
                #endif
                self.logger.info("flashMC output: '%s'", line)
            #endif
        #endwhile

        if retc:
            self.logger.error("%s failed with code %d", defines.flashMcCommand, retc)
        #endif

        sleep(2)
        self.portLock.release()

        return False if retc else True
    #enddef


    def reset(self):
        import gpio
        gpio.setup(131, gpio.OUT)
        gpio.set(131, 1)
        sleep(1/1000000)
        gpio.set(131, 0)
    #enddef


    def getStateBits(self, request = None):
        if not request:
            request = self._statusBits.keys()
        #endif
        bits = self.doGetBoolList("?", bitCount = 16)
        if len(bits) != 16:
            self.logger.warning("State bits count not match! (%s)", str(bits))
            return None
        else:
            retval = {}
            for name in request:
                try:
                    retval[name] = bits[self._statusBits[name]]
                except Exception:
                    self.logger.exception("exception:")
                    return None
                #endtry
            #endfor
            return retval
        #endif
    #enddef

#endclass


class DummyMotConCom(MotConCom):
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.debug = self
        self.port = self
        super().__init__("MC_Dummy")
    #enddef

    def getStateBits(self, request=None):
        if not request:
            request = self._statusBits.keys()
        #endif

        retval = {}
        for name in request:
            retval[name] = False
        #endfor

        return retval
    #enddef

    def do(self, cmd, *args):
        self.logger.debug(f"mcc.do called while using dummy MotConCom: {cmd} {args}")
    #enddef

    def start(self) -> None:
        pass
    #enddef

    def is_open(self) -> bool:
        return False
    #enddef

    def close(self) -> None:
        pass
    #enddef

    def showItems(self, *args, **kwargs):
        self.logger.debug("mcc.debug.showItems called while using dummy MotConCom")
    #enddef

    def exit(self):
        pass
    #enddef
#endclass


def safe_call(default_value, exceptions):
    """
    Decorate method to be safe to call

    Wraps method call in try-cache block, cache excptions and in case of troubles log exception and return
    safe default value.

    :param default_value: Value to return if wrapped function failes
    :param exceptions: Exceptions to catch
    :return: Decorator
    """
    def decor(method):
        def func(self, *args, **kwargs):
            try:
                return method(self, *args, **kwargs)
            except exceptions:
                self.logger.exception(f"Call to {method.__name__} failed, returning safe default")
                return default_value
            #endtry
        return func
    return decor
#enddef


class Hardware(object):

    def __init__(self, hwConfig, config):
        self.logger = logging.getLogger(__name__)
        self.hwConfig = hwConfig
        self.config = config

        self._tiltSynced = False
        self._towerSynced = False

        self._lastTiltProfile = None
        self._lastTowerProfile = None

        self._tiltToPosition = 0
        self._towerToPosition = 0

        self._fanFailed = False
        self._coolDownCounter = 0
        self._ledTempIdx = 0

        # (mode, speed)
        self._powerLedStates= { 'normal' : (1, 2), 'warn' : (2, 10), 'error' : (3, 15), 'off' : (3, 64) }

        self._tiltProfiles = {
                'homingFast'    : 0,
                'homingSlow'    : 1,
                'moveFast'      : 2,
                'moveSlow'      : 3,
                'layerMoveSlow' : 4,
                'layerRelease'  : 5,
                'layerMoveFast' : 6,
                '<reserved2>'   : 7,
                }
        self._towerProfiles = {
                'homingFast'    : 0,
                'homingSlow'    : 1,
                'moveFast'      : 2,
                'moveSlow'      : 3,
                'layer'         : 4,
                'layerMove'     : 5,
                '<reserved2>'   : 6,
                'resinSensor'   : 7,
                }

        # get sorted profiles names
        self._tiltProfileNames = [x[0] for x in sorted(list(self._tiltProfiles.items()), key=lambda kv: kv[1])]
        self._towerProfileNames = [x[0] for x in sorted(list(self._towerProfiles.items()), key=lambda kv: kv[1])]

        self.tiltAdjust = {
            #               -2      -1      0     +1     +2
            'homingFast': [[20,5],[20,6],[20,7],[21,9],[22,12]],
            'homingSlow': [[16,3],[16,5],[16,7],[16,9],[16,11]]
        }

        self.towerAdjust = {
            #               -2      -1      0     +1     +2
            'homingFast': [[22,0],[22,2],[22,4],[22,6],[22,8]],
            'homingSlow': [[14,0],[15,0],[16,1],[16,3],[16,5]]
        }

        self._fansNames = {
                0 : _("UV LED fan"),
                1 : _("blower fan"),
                2 : _("rear fan"),
                }

        self._fansRpm = {
                0 : 0,
                1 : 0,
                2 : 0,
                }

        self._fansEnabled = {
                0 : False,
                1 : False,
                2 : False,
                }

        self._sensorsNames = {
                0 : _("UV LED temperature"),
                1 : _("Ambient temperature"),
                2 : _("<reserved1>"),
                3 : _("<reserved2>"),
                }

        self._tiltMin = -12800        # whole turn
        self._tiltEnd = 6016    #top deadlock
        self._tiltMax = self._tiltEnd
        self._tiltCalibStart = 4352 
        self._towerMin = -self.hwConfig.calcMicroSteps(155)
        self._towerAboveSurface = -self.hwConfig.calcMicroSteps(145)
        self._towerMax = self.hwConfig.calcMicroSteps(310)
        self._towerEnd = self.hwConfig.calcMicroSteps(150)
        self._towerCalibPos = self.hwConfig.calcMicroSteps(1)
        self._towerResinStartPos = self.hwConfig.calcMicroSteps(36)
        self._towerResinEndPos = self.hwConfig.calcMicroSteps(1)
        self._tiltSyncRetries = None
        self._towerSyncRetries = None

        self.mcc = MotConCom("MC_Main")
        self.realMcc = self.mcc
        self.boardData = self.readCpuSerial()
    #enddef


    def start(self):
        self.mcc.start()
    #enddef


    def __del__(self):
        self.exit()
    #enddef


    def exit(self):
        self.mcc.exit()
    #enddef


    def connectMC(self, waitPage, returnPage):

        errorMessage = self.mcc.connect(self.hwConfig.MCversionCheck)
        if errorMessage:
            self.logger.warning("motion controller error: %s", errorMessage)

            waitPage.fill(line1 = _("Updating motion controller firmware"))
            waitPage.show()

            if not self.mcc.flash(self.hwConfig.MCBoardVersion):
                self.ahojBabi(waitPage, _("Motion controller update has failed!"))
            #endif

            errorMessage = self.mcc.connect(self.hwConfig.MCversionCheck)
            if errorMessage:
                self.logger.error("motion controller error: %s", errorMessage)
                self.ahojBabi(waitPage, errorMessage)
            #endif

            waitPage.showItems(line1 = _("Erasing EEPROM"))
            self.eraseEeprom()

            returnPage.show()
        #endif

        self.initDefaults()
    #enddef


    def initDefaults(self):
        self.motorsRelease()
        self.setFansRpm({
            0 : self.hwConfig.fan1Rpm,
            1 : self.hwConfig.fan2Rpm,
            2 : self.hwConfig.fan3Rpm,
            })
        self.uvLedPwm = self.hwConfig.uvPwm
        self.powerLedPwm = self.hwConfig.pwrLedPwm
        self.resinSensor(False)
        self.stopFans()
    #enddef


    def ahojBabi(self, waitPage, message):
        waitPage.show()
        waitPage.showItems(line1 = _("Fatal error"), line2 = message)
        while True:
            waitPage.showItems(line3 = _("Please contact tech support!"))
            sleep(1)
            waitPage.showItems(line3 = "")
            sleep(1)
        #endwhile
    #enddef


    def flashMC(self, waitPage, returnPage):
        waitPage.fill(line1 = _("Forced update of the motion controller firmware"))
        waitPage.show()
        self.mcc.flash(self.hwConfig.MCBoardVersion)
        self.connectMC(waitPage, returnPage)
    #enddef


    def switchToDummy(self):
        self.mcc = DummyMotConCom()
    #enddef


    def switchToMC(self, waitPage, actualPage):
        self.mcc = self.realMcc
        self.connectMC(waitPage, actualPage)
    #enddef

    @property
    def tilt_end(self) -> int:
        return self._tiltEnd

    @property
    def mcFwVersion(self):
        return self.mcc.MCFWversion
    #enddef


    @property
    def mcFwRevision(self):
        return self.mcc.MCFWrevision
    #enddef


    @property
    def mcBoardRevisionBin(self):
        return (self.mcc.MCBoardRevision[1], (self.mcc.MCBoardRevision[0]))
    #enddef


    @property
    def mcBoardRevision(self):
        if self.mcc.MCBoardRevision[1] > -1 and self.mcc.MCBoardRevision[0] > -1:
            return "%d%s" % (self.mcc.MCBoardRevision[1], chr(self.mcc.MCBoardRevision[0] + ord('a')))
        else:
            return "unk"
        #endif
    #enddef


    @property
    def mcSerialNo(self):
        return self.mcc.MCserial
    #enddef


    @property
    def cpuSerialNo(self):
        return self.boardData[0]
    #enddef


    @property
    def isKit(self):
        return self.boardData[1]
    #enddef


    def readCpuSerial(self):
        ot = { 0 : "CZP" }
        serial = "*INVALID*"
        is_kit = True   # kit is more strict
        try:
            with open(defines.cpuSNFile, 'rb') as nvmem:
                s = bitstring.BitArray(bytes = nvmem.read())
            #endwith

            mac, mcs1, mcs2, snbe = s.unpack('pad:192, bits:48, uint:8, uint:8, pad:224, uintbe:64')
            mcsc = mac.count(1)
            if mcsc != mcs1 or mcsc ^ 255 != mcs2:
                self.logger.error("MAC checksum FAIL (is %02x:%02x, should be %02x:%02x)" % (mcs1, mcs2, mcsc, mcsc ^ 255))
            else:
                hex = ":".join(re.findall("..", mac.hex))
                self.logger.info("MAC: %s (checksum %02x:%02x)", hex, mcs1, mcs2)

                # byte order change
                sn = bitstring.BitArray(length = 64, uintle = snbe)

                scs2, scs1, snnew = sn.unpack('uint:8, uint:8, bits:48')
                scsc = snnew.count(1)
                if scsc != scs1 or scsc ^ 255 != scs2:
                    self.logger.warn("SN checksum FAIL (is %02x:%02x, should be %02x:%02x), getting old SN format" % (scs1, scs2, scsc, scsc ^ 255))
                    sequence_number, is_kit, ean_pn, year, week, origin = sn.unpack('pad:14, uint:17, bool, uint:10, uint:6, pad:2, uint:6, pad:2, uint:4')
                    prefix = "*"
                else:
                    sequence_number, is_kit, ean_pn, year, week, origin = snnew.unpack('pad:4, uint:17, bool, uint:10, uint:6, uint:6, uint:4')
                    prefix = ""
                #endif
                serial = "%s%3sX%02u%02uX%03uX%c%05u" % (prefix, ot.get(origin, "UNK"), week, year, ean_pn, "K" if is_kit else "C", sequence_number)
                self.logger.info("SN: %s", serial)
            #endif
        except Exception:
            self.logger.exception("CPU serial:")
        #endtry
        return (serial, is_kit)
    #enddef


    def checkFailedBoot(self):
        '''
        Check for failed boot by comparing current and last boot slot
        :return: True is last boot failed, false otherwise
        '''
        try:
            # Get slot statuses
            rauc = pydbus.SystemBus().get("de.pengutronix.rauc", "/")["de.pengutronix.rauc.Installer"]
            status = rauc.GetSlotStatus()
            a = status[0][1]['boot-status']
            b = status[2][1]['boot-status']

            if a == 'good' and b == 'good':
                # Device is booting fine, remove stamp
                if os.path.isfile(defines.bootFailedStamp):
                    os.remove(defines.bootFailedStamp)
                #endif
                return False
            else:
                # Device has boot problems
                if os.path.isfile(defines.bootFailedStamp):
                    # The problem is already reported
                    return False
                else:
                    # This is a new problem, create stamp, report problem
                    if not os.path.exists(defines.persistentStorage):
                        os.makedirs(defines.persistentStorage)
                    #endif
                    open(defines.bootFailedStamp, 'a').close()
                    return True
                #endif
            #endif
        except:
            self.logger.exception("Failed to check for failed boot")
            # Something went wrong during check, expect the worst
            return True
        #endtry
    #enddef


    def eraseEeprom(self):
        self.mcc.do("!eecl")
        self.mcc.do("!rst")  # FIXME MC issue
        sleep(1.5)  # FIXME another MC issue (avoid using MC before it is initialized)
    #enddef


    def getTiltProfilesNames(self):
        self.logger.debug(str(self._tiltProfileNames))
        return list(self._tiltProfileNames)
    #enddef


    def getTowerProfilesNames(self):
        self.logger.debug(str(self._towerProfileNames))
        return list(self._towerProfileNames)
    #enddef


    def getTiltProfiles(self):
        return self.getProfiles("?ticf")
    #enddef


    def getTowerProfiles(self):
        return self.getProfiles("?twcf")
    #enddef


    def getProfiles(self, getProfileDataCmd):
        profiles = []
        for profId in range(8):
            try:
                profData = self.mcc.do(getProfileDataCmd, profId).split(" ")
                profiles.append([int(x) for x in profData])
            except Exception:
                self.logger.exception("parse profile:")
                profiles.append(list((-1, -1, -1, -1, -1, -1, -1)))
            #endtry
        #endfor
        return profiles
    #enddef


    def setTiltProfiles(self, profiles):
        return self.setProfiles(profiles, "!tics", "!ticf")
    #enddef


    def setTowerProfiles(self, profiles):
        return self.setProfiles(profiles, "!twcs", "!twcf")
    #enddef


    def setProfiles(self, profiles, setProfileCmd, setProfileDataCmd):
        for profId in range(8):
            self.mcc.do(setProfileCmd, profId)
            self.mcc.do(setProfileDataCmd, *profiles[profId])
        #endfor
    #enddef


    def setTiltTempProfile(self, profileData):
        return self.setTempProfile(profileData, "!tics", "!ticf")
    #enddef


    def setTowerTempProfile(self, profileData):
        return self.setTempProfile(profileData, "!twcs", "!twcf")
    #enddef


    def setTempProfile(self, profileData, setProfileCmd, setProfileDataCmd):
        self.mcc.do(setProfileCmd, -1)
        self.mcc.do(setProfileDataCmd, *profileData)
    #enddef


    def getStallguardBuffer(self):
        samplesList = list()
        samplesCount = self.mcc.doGetInt("?sgbc")
        while samplesCount > 0:
            try:
                samples = self.mcc.doGetIntList("?sgbd", base = 16)
                samplesCount -= len(samples)
                samplesList.extend(samples)
            except MotionControllerException as e:
                self.logger.exception("Problem reading stall guard buffer")
                break
            #endtry
        #endwhile
        return samplesList
    #enddef


    def beep(self, frequency, lenght):
        if not self.hwConfig.mute:
            self.mcc.do("!beep", frequency, int(lenght * 1000))
        #endif
    #enddef


    def beepEcho(self):
        self.beep(1800, 0.05)
    #enddef


    def beepRepeat(self, count):
        for num in range(count):
            self.beep(1800, 0.1)
            sleep(0.5)
        #endfor
    #enddef


    def beepAlarm(self, count):
        for num in range(count):
            self.beep(1900, 0.05)
            sleep(0.25)
        #endfor
    #enddef


    def powerLed(self, state):
        mode, speed = self._powerLedStates.get(state, (1, 1))
        self.powerLedMode = mode
        self.powerLedSpeed = speed
    #enddef


    @property
    def powerLedMode(self):
        return self.mcc.doGetInt("?pled")
    #enddef

    @powerLedMode.setter
    def powerLedMode(self, value):
        self.mcc.do("!pled", value)
    #enddef


    @property
    def powerLedPwm(self):
        try:
            pwm = self.mcc.do("?ppwm")
            return int(pwm) * 5
        except MotionControllerException:
            self.logger.exception("Failed to read power led pwm")
            return -1
        #endtry
    #enddef


    @powerLedPwm.setter
    def powerLedPwm(self, pwm):
        try:
            self.mcc.do("!ppwm", int(pwm / 5))
        except MotionControllerException:
            self.logger.exception("Failed to set power led pwm")
        #endtry
    #enddef


    @property
    @safe_call(-1, MotionControllerException)
    def powerLedSpeed(self):
        return self.mcc.doGetInt("?pspd")
    #enddef


    @powerLedSpeed.setter
    @safe_call(None, MotionControllerException)
    def powerLedSpeed(self, speed):
        self.mcc.do("!pspd", speed)
    #enddef


    def shutdown(self):
        self.mcc.do("!shdn", 5)
    #enddef


    def uvLed(self, state, time = 0):
        self.mcc.do("!uled", 1 if state else 0, int(time))        
    #enddef


    @safe_call([0, 0], (ValueError, MotionControllerException))
    def getUvLedState(self):
        uvData = self.mcc.doGetIntList("?uled")
        if 0 < len(uvData) < 3:
            return uvData if len(uvData) == 2 else list((uvData[0], 0))
        else:
            raise ValueError(f"UV data count not match! ({uvData})")
        #endif
    #enddef


    @property
    def uvLedPwm(self):
        return self.mcc.doGetInt("?upwm")
    #enddef

    @uvLedPwm.setter
    def uvLedPwm(self, pwm):
        self.mcc.do("!upwm", pwm)
    #enddef


    @safe_call([0], (MotionControllerException, ValueError))
    def getUvStatistics(self):
        uvData = self.mcc.doGetIntList("?usta") #time counter [s] #TODO add uv average current, uv average temperature
        if len(uvData) != 1:
            raise ValueError(f"UV statistics data count not match! ({uvData})")
        #endif
        return uvData
    #enddef


    def saveUvStatistics(self):
        self.mcc.do("!usta", 0)
    #enddef


    def clearUvStatistics(self):    # call if UV led was replaced
        self.mcc.do("!usta", 1)
    #enddef

    @safe_call([0, 0, 0, 0], (ValueError, MotionControllerException))
    def getVoltages(self):
        volts = self.mcc.doGetIntList("?volt", multiply = 0.001)
        if len(volts) != 4:
            raise ValueError(f"Volts count not match! ({volts})")
        #endif
        return volts
    #enddef


    def cameraLed(self, state):
        self.mcc.do("!cled", 1 if state else 0)
    #enddef


    def getCameraLedState(self):
        return self.mcc.doGetBool("?cled")
    #enddef


    def resinSensor(self, state):
        """Enable/Disable resin sensor"""
        self.mcc.do("!rsen", 1 if state else 0)
    #enddef


    def getResinSensor(self):
        """
        Read resin sensor enabled
        :return: True if enabled, False otherwise
        """
        return self.mcc.doGetBool("?rsen")
    #enddef


    def getResinSensorState(self):
        """
        Read resin sensor value
        :return: True if resin is detected, False otherwise
        """
        return self.mcc.doGetBool("?rsst")
    #enddef

    @safe_call(False, MotionControllerException)
    def isCoverClosed(self):
        return self.checkState('cover')
    #enddef


    def getPowerswitchState(self):
        return self.checkState('button')
    #enddef


    @safe_call(False, MotionControllerException)
    def checkState(self, name):
        state = self.mcc.getStateBits((name,))
        return state[name]
    #enddef


    def startFans(self):
        self.setFans({ 0 : True, 1 : True, 2 : True })
    #enddef


    def stopFans(self):
        self.setFans({ 0 : False, 1 : False, 2 : False })
    #enddef


    def setFans(self, fans = None):
        if fans:
            self._fansEnabled.update(fans)
        #endif
        out = list()
        for key in sorted(self._fansEnabled):
            out.append(self._fansEnabled[key] and self._fansRpm[key] >= defines.fanMinRPM)
        #endfor
        self.mcc.doSetBoolList("!fans", out)
        self.mcc.doSetBoolList("!fmsk", out)
    #enddef


    def getFans(self, request = (0, 1, 2)):
        return self.getFansBits("?fans", request)
    #enddef


    def getFanCheckMask(self, request = (0, 1, 2)):
        return self.getFansBits("?fmsk", request)
    #enddef

    @safe_call({ 0: False, 1: False, 2: False }, (MotionControllerException, ValueError))
    def getFansError(self):
        state = self.mcc.getStateBits(('fans',))
        if not 'fans' in state:
            raise ValueError(f"'fans' not in state: {state}")
        #endif
        return self.getFansBits("?fane", (0, 1, 2))
    #enddef


    def getFansBits(self, cmd, request):
        try:
            bits = self.mcc.doGetBoolList(cmd, bitCount = 3)
            if len(bits) != 3:
                raise ValueError(f"Fans bits count not match! {bits}")
            #endif
            retval = {}
            for idx in request:
                try:
                    retval[idx] = bits[idx]
                except Exception:
                    self.logger.exception("exception:")
                    return dict.fromkeys(request, False)
                #endtry
            #endfor
            return retval
        except (MotionControllerException, ValueError):
            self.logger.exception("getFansBits failed")
            return dict.fromkeys(request, False)
        #endtry
    #enddef


    def setFansRpm(self, rpms):
        self._fansRpm.update(rpms)
        out = list()
        for key in sorted(self._fansRpm):
            if self._fansRpm[key] < defines.fanMinRPM:
                out.append(defines.fanMinRPM)
            else:
                out.append(self._fansRpm[key])
            #endif
        #endfor
        self.mcc.do("!frpm", " ".join(map(str, out)))
        self.setFans()
    #enddef


    def getFansRpm(self, request = (0, 1, 2)):
        try:
            rpms = self.mcc.doGetIntList("?frpm", multiply = 1)
            if not rpms or len(rpms) != 3:
                raise ValueError(f"RPMs count not match! ({rpms})")
            #endif
            retval = {}
            for idx in request:
                try:
                    retval[idx] = rpms[idx]
                except Exception:
                    self.logger.exception("exception:")
                    return dict.fromkeys(request, 0)
                #endtry
            #endfor
            return retval
        except (MotionControllerException, ValueError):
            self.logger.exception(f"getFansRpm failed")
            return dict.fromkeys(request, 0)
        #endtry
    #enddef


    def getFanName(self, fanNumber):
        return self._fansNames.get(fanNumber, _("unknown fan"))
    #enddef


    @safe_call([-273.2, -273.2, -273.2, -273.2], (MotionControllerException, ValueError))
    def getMcTemperatures(self):
        temps = self.mcc.doGetIntList("?temp", multiply = 0.1)
        if len(temps) != 4:
            raise ValueError(f"TEMPs count not match! ({temps})")
        #endif
        self.logger.info("Temperatures [C]: %s", " ".join(["%.1f" % x for x in temps]))
        return temps
    #enddef


    def getUvLedTemperature(self):
        return self.getMcTemperatures()[self._ledTempIdx]
    #endif


    def getSensorName(self, sensorNumber):
        return self._sensorsNames.get(sensorNumber, _("unknown sensor"))
    #enddef


    @safe_call(-273.2, Exception)
    def getCpuTemperature(self):
        with open(defines.cpuTempFile, "r") as f:
            return round((int(f.read()) / 1000.0), 1)
        #endwith
    #enddef


    # --- motors ---


    def motorsRelease(self):
        self.mcc.do("!motr")
        self._tiltSynced = False
        self._towerSynced = False
    #enddef


    def motorsHold(self):
        self.setTiltCurrent(defines.tiltHoldCurrent)
        self.setTowerCurrent(defines.towerHoldCurrent)
    #enddef


    def towerHoldTiltRelease(self):
        self.mcc.do("!ena 1")
        self._tiltSynced = False
    #enddef


    # --- tower ---


    def towerHomeCalibrateWait(self):
        self.mcc.do("!twhc")
        homingStatus = 1
        while homingStatus > 0: # not done and not error
            homingStatus = self.mcc.doGetInt("?twho")
            sleep(0.1)
        #endwhile
    #enddef


    def towerSync(self, retries: Optional[int] = 2):
        ''' home is at top position, retries = None is infinity '''
        self._towerSyncRetries = retries
        self.mcc.do("!twho")
    #enddef


    @safe_call(False, MotionControllerException)
    def isTowerSynced(self):
        """
        TODO:   This method looks like state check, but actually it does much more. Such an counter-intuitive method
                deserves rewrite or at last proper documnetation.
        """
        homingStatus = self.mcc.doGetInt("?twho")
        if homingStatus > 0:    # not done and not error
            return False
        elif not homingStatus:
            self.setTowerPosition(self.hwConfig.towerHeight)
            self._towerSynced = True
            return True
        else:
            self.logger.warning("Tower homing failed!")
            self.mcc.debug.showItems(towerFailed = "homing Fast/Slow")
            # repeat count, None is infinity
            if self._towerSyncRetries is None or self._towerSyncRetries:
                if self._towerSyncRetries:
                    self._towerSyncRetries -= 1
                #endif
                self.mcc.do("!twho")
                return False
            else:
                self.logger.error("Tower homing max tries reached!")
                return True
            #endif
        #endif
    #enddef


    def towerSyncWait(self):
        self.towerSync(None)
        while not self.isTowerSynced():
            sleep(0.1)
        #endwhile
        return not self.towerSyncFailed()
    #enddef


    def towerSyncFailed(self):
        return self._towerSyncRetries == 0
    #enddef


    def towerMoveAbsoluteWait(self, position):
        self.towerMoveAbsolute(position)
        while not self.isTowerOnPosition():
            sleep(0.1)
        #endwhile
    #enddef


    @safe_call(None, MotionControllerException)
    def towerMoveAbsolute(self, position):
        self._towerToPosition = position
        self.mcc.do("!twma", position)
    #enddef


    def towerToPosition(self, mm):
        self.towerMoveAbsolute(self.hwConfig.calcMicroSteps(mm))
    #enddef


    #TODO use !brk instead. Motor might stall at !mot 0
    def towerStop(self):
        self.mcc.do("!mot", 0)
    #enddef


    def isTowerMoving(self):
        if self.mcc.doGetInt("?mot") & 1:
            return True
        #endif
        return False
    #enddef


    @safe_call(False, MotionControllerException)
    def isTowerOnPosition(self, retries = None):
        ''' check dest. position, retries = None is infinity '''
        self._towerPositionRetries = retries
        if self.isTowerMoving():
            return False
        #endif
        while self._towerToPosition != self.getTowerPositionMicroSteps():
            if self._towerPositionRetries is None or self._towerPositionRetries:
                if self._towerPositionRetries:
                    self._towerPositionRetries -= 1
                #endif
                self.logger.warning("Tower is not on required position! Sync forced.")
                self.mcc.debug.showItems(towerFailed = self._lastTowerProfile)
                profileBackup = self._lastTowerProfile
                self.towerSyncWait()
                self.setTowerProfile(profileBackup)
                self.towerMoveAbsolute(self._towerToPosition)
                while self.isTowerMoving():
                    sleep(0.1)
                #endwhile
            else:
                self.logger.error("Tower position max tries reached!")
                break
        #endwhile
        return True
    #enddef


    def towerPositonFailed(self):
        return self._towerPositionRetries == 0
    #enddef


    def towerToZero(self):
        self.towerMoveAbsolute(self.hwConfig.calibTowerOffset)
    #enddef


    def isTowerOnZero(self):
        return self.isTowerOnPosition()
    #enddef


    def towerToTop(self):
        self.towerMoveAbsolute(self.hwConfig.towerHeight)
    #enddef


    def isTowerOnTop(self):
        return self.isTowerOnPosition()
    #enddef


    def setTowerOnMax(self):
        self.setTowerPosition(self._towerEnd)
    #enddef


    def towerToMax(self):
        self.towerMoveAbsolute(self._towerMax)
    #enddef


    def isTowerOnMax(self):
        stopped = not self.isTowerMoving()
        if stopped:
            self.setTowerOnMax()
        #endif
        return stopped
    #enddef


    def towerToMin(self):
        self.towerMoveAbsolute(self._towerMin)
    #enddef


    def isTowerOnMin(self):
        stopped = not self.isTowerMoving()
        if stopped:
            self.setTowerPosition(0)
        #endif
        return stopped
    #enddef


    @safe_call(None, MotionControllerException)
    def setTowerPosition(self, position):
        self.mcc.do("!twpo", position)
        self.mcc.debug.showItems(towerPositon = position)
    #enddef


    @safe_call("ERROR", Exception)
    def getTowerPosition(self):
        steps = self.getTowerPositionMicroSteps()
        return "%.3f mm" % self.hwConfig.calcMM(int(steps))
    #enddef


    def getTowerPositionMicroSteps(self):
        steps = self.mcc.doGetInt("?twpo")
        self.mcc.debug.showItems(towerPositon = steps)
        return steps
    #enddef


    @safe_call(None, (ValueError, MotionControllerException))
    def setTowerProfile(self, profile):
        self._lastTowerProfile = profile
        profileId = self._towerProfiles.get(profile, None)
        if profileId is None:
            raise ValueError(f"Invalid tower profile '{profile}'")
        #endif
        self.mcc.debug.showItems(towerProfile = profile)
        self.mcc.do("!twcs", profileId)
    #enddef


    @safe_call(None, (MotionControllerException, ValueError))
    def setTowerCurrent(self, current):
        return
#        if 0 <= current <= 63:
#            self.mcc.do("!twcu", current)
#        else:
#            self.logger.error("Invalid tower current %d", current)
        #endif
    #enddef


    #  5.0 mm -  35 % -  68.5 ml
    # 10.0 mm -  70 % - 137.0 ml
    # 14.5 mm - 100 % - 200.0 ml

    # 35 % -  70 % : 1.0 mm = 13.7 ml
    # 70 % - 100 % : 0.9 mm = 12.5 ml

    @safe_call(0, MotionControllerException)
    def getResinVolume(self):
        self.setTowerProfile('homingFast')
        self.towerMoveAbsoluteWait(self._towerResinStartPos) # move quickly to safe distance
        self.resinSensor(True)
        sleep(1)
        self.setTowerProfile('resinSensor')
        self.mcc.do("!rsme", self._towerResinStartPos - self._towerResinEndPos) # relative movement!
        while self.isTowerMoving():
            sleep(0.1)
        #endwhile
        position = self.getTowerPositionMicroSteps()
        self.resinSensor(False)
        if position == self._towerResinEndPos:
            return 0
        else:
            posMM = self.hwConfig.calcMM(position)
            if posMM < 10:  # cca 137 ml
                volume = posMM * 13.7
            else:
                volume = posMM * 0.9 * 12.5
            #endif
            return int(round(volume / 10.0) * 10)
        #endif
    #enddef


    def calcPercVolume(self, volume):
        return int(ceil(volume * 0.05) * 10)
    #enddef


    # --- tilt ---


    def tiltHomeCalibrateWait(self):
        self.mcc.do("!tihc")
        homingStatus = 1
        while homingStatus > 0: # not done and not error
            homingStatus = self.mcc.doGetInt("?tiho")
            sleep(0.1)
        #endwhile
    #enddef


    def tiltSync(self, retries = None):
        ''' home at bottom position, retries = None is infinity '''
        self._tiltSyncRetries = retries
        self.mcc.do("!tiho")
    #enddef


    @safe_call(False, MotionControllerException)
    def isTiltSynced(self):
        homingStatus = self.mcc.doGetInt("?tiho")
        if homingStatus > 0: # not done and not error
            return False
        elif not homingStatus:
            self.setTiltPosition(0)
            self._tiltSynced = True
            return True
        else:
            self.logger.warning("Tilt homing failed!")
            self.mcc.debug.showItems(tiltFailed = "homing Fast/Slow")
            # repeat count, None is infinity
            if self._tiltSyncRetries is None or self._tiltSyncRetries:
                if self._tiltSyncRetries:
                    self._tiltSyncRetries -= 1
                #endif
                self.mcc.do("!tiho")
                return False
            else:
                self.logger.error("Tilt homing max tries reached!")
                return True
            #endif
        #endif
    #enddef


    def tiltSyncWait(self, retries = None):
        self.tiltSync(retries)
        while not self.isTiltSynced():
            sleep(0.1)
        #endwhile
        return not self.tiltSyncFailed()
    #enddef


    def tiltSyncFailed(self):
        return self._tiltSyncRetries == 0
    #enddef


    def tiltMoveAbsolute(self, position):
        self._tiltToPosition = position
        self.mcc.do("!tima", position)
    #enddef


    def tiltStop(self):
        self.mcc.do("!mot", 0)
    #enddef


    def isTiltMoving(self):
        if self.mcc.doGetInt("?mot") & 2:
            return True
        #endif
        return False
    #enddef


    def isTiltOnPosition(self):
        if self.isTiltMoving():
            return False
        #endif
        if self.getTiltPositionMicroSteps() != 0:
            self.logger.warning("Tilt is not on required position! Sync forced. Actual position: %d", self.getTiltPositionMicroSteps())
            self.mcc.debug.showItems(tiltFailed = self._lastTiltProfile)
            profileBackup = self._lastTiltProfile
            self.tiltSyncWait()
            self.setTiltProfile(profileBackup)
            self.tiltMoveAbsolute(self._tiltToPosition)
            while self.isTiltMoving():
                sleep(0.1)
            #endwhile
        #endwhile

        return True
    #enddef


    def tiltDown(self):
        self.tiltMoveAbsolute(0)
    #endif


    def isTiltDown(self):
        return self.isTiltOnPosition()
    #enddef


    def tiltDownWait(self):
        self.tiltDown()
        while not self.isTiltDown():
            sleep(0.1)
        #endwhile
    #enddef


    def tiltUp(self):
        self.tiltMoveAbsolute(self.hwConfig.tiltHeight)
    #enddef


    def isTiltUp(self):
        return self.isTiltOnPosition()
    #enddef


    def tiltUpWait(self):
        self.tiltUp()
        while not self.isTiltUp():
            sleep(0.1)
        #endwhile
    #enddef


    def tiltToMax(self):
        self.tiltMoveAbsolute(self._tiltMax)
    #enddef


    def isTiltOnMax(self):
        stopped = not self.isTiltMoving()
        if stopped:
            self.setTiltPosition(self._tiltEnd)
        #endif
        return stopped
    #enddef


    def tiltToMin(self):
        self.tiltMoveAbsolute(self._tiltMin)
    #enddef


    def isTiltOnMin(self):
        stopped = not self.isTiltMoving()
        if stopped:
            self.setTiltPosition(0)
        #endif
        return stopped
    #enddef


    def tiltLayerDownWait(self, slowMove = False):
        if slowMove:
            tiltProfile = self.hwConfig.tuneTilt[0]
        else:
            tiltProfile = self.hwConfig.tuneTilt[1]
        #endif

        # initial release movement with optional sleep at the end
        self.setTiltProfile(self._tiltProfileNames[tiltProfile[0]])
        if tiltProfile[1] > 0:
            self.tiltMoveAbsolute(self.getTiltPositionMicroSteps() - tiltProfile[1])
            while self.isTiltMoving():
                sleep(0.1)
            #endwhile
        #endif
        sleep(tiltProfile[2] / 1000.0)

        # next movement may be splited
        self.setTiltProfile(self._tiltProfileNames[tiltProfile[3]])
        movePerCycle = int(self.getTiltPositionMicroSteps() / tiltProfile[4])
        for i in range(tiltProfile[4]):
            self.tiltMoveAbsolute(self.getTiltPositionMicroSteps() - movePerCycle)
            while self.isTiltMoving():
                sleep(0.1)
            #endwhile
            sleep(tiltProfile[5] / 1000.0)
        #endfor

        # if not already in endstop ensure we end up at defined bottom position
        if not self.checkState('endstop'):
            self.tiltMoveAbsolute(-defines.tiltHomingTolerance)
            while self.isTiltMoving():
                sleep(0.1)
            #endwhile
        #endif

        # check if tilt is on endstop
        if self.checkState('endstop'):
            return True
        #endif

        # unstuck
        self.logger.warning("Tilt unstucking")
        self.setTiltProfile("layerRelease")
        count = 0
        step = 128
        while count < self._tiltEnd and not self.checkState('endstop'):
            self.setTiltPosition(step)
            self.tiltMoveAbsolute(0)
            while self.isTiltMoving():
                sleep(0.1)
            #endwhile
            count += step
        #endwhile
        return self.tiltSyncWait(1)
    #enddef


    def tiltLayerUpWait(self):
        self.setTiltProfile(self._tiltProfileNames[self.hwConfig.tuneTilt[2][0]])
        self.tiltMoveAbsolute(self.hwConfig.tiltHeight - self.hwConfig.tuneTilt[2][1])
        while self.isTiltMoving():
            sleep(0.1)
        #endwhile
        sleep(self.hwConfig.tuneTilt[2][2]/1000.0)
        self.setTiltProfile(self._tiltProfileNames[self.hwConfig.tuneTilt[2][3]])

        #finish move may be also splited in multiple sections
        movePerCycle = int((self.hwConfig.tiltHeight - self.getTiltPositionMicroSteps()) / self.hwConfig.tuneTilt[2][4])
        for i in range(self.hwConfig.tuneTilt[2][4]):
            self.tiltMoveAbsolute(self.getTiltPositionMicroSteps() + movePerCycle)
            while self.isTiltMoving():
                sleep(0.1)
            #endwhile
            sleep(self.hwConfig.tuneTilt[2][5] / 1000.0)
        #endfor

        #reduce tilt current to prevent overheat
        self.setTiltCurrent(defines.tiltHoldCurrent)
    #enddef


    def setTiltPosition(self, position):
        self.mcc.do("!tipo", position)
        self.mcc.debug.showItems(tiltPosition = position)
    #enddef


    # TODO: Get rid of this
    # TODO: Fix inconsistency getTowerPosition returns formated string with mm
    # TODO: Property could handle this a bit more consistently
    @safe_call("ERROR", MotionControllerException)
    def getTiltPosition(self):
        return self.getTiltPositionMicroSteps()
    #enddef


    def getTiltPositionMicroSteps(self):
        steps = self.mcc.doGetInt("?tipo")
        self.mcc.debug.showItems(tiltPosition = steps)
        return steps
    #enddef


    def setTiltProfile(self, profile):
        self._lastTiltProfile = profile
        profileId = self._tiltProfiles.get(profile, None)
        if profileId is not None:
            self.mcc.debug.showItems(tiltProfile = profile)
            self.mcc.do("!tics", profileId)
        else:
            self.logger.error("Invalid tilt profile '%s'", profile)
        #endif
    #enddef


    @safe_call(None, (MotionControllerException, ValueError))
    def setTiltCurrent(self, current):
        return
#        if 0 <= current <= 63:
#            self.mcc.do("!ticu", current)
#        else:
#            self.logger.error("Invalid tilt current %d", current)
        #endif
    #enddef


    def tiltGotoFullstep(self):
        self.mcc.do("!tigf")
    #enddef


    def stirResin(self):
        for i in range(self.hwConfig.stirringMoves):
            self.setTiltProfile('homingFast')
            # do not verify end positions
            self.tiltUp()
            while self.isTiltMoving():
                sleep(0.1)
            #endwhile
            self.tiltDown()
            while self.isTiltMoving():
                sleep(0.1)
            #endwhile
            self.tiltSyncWait()
        #endfor
    #enddef

    def updateMotorSensitivity(self, tiltSensitivity = 0, towerSensitivity = 0):
        # adjust tilt profiles
        profiles = self.getTiltProfiles()
        profiles[0][4] = self.tiltAdjust['homingFast'][tiltSensitivity + 2][0]
        profiles[0][5] = self.tiltAdjust['homingFast'][tiltSensitivity + 2][1]
        profiles[1][4] = self.tiltAdjust['homingSlow'][tiltSensitivity + 2][0]
        profiles[1][5] = self.tiltAdjust['homingSlow'][tiltSensitivity + 2][1]
        self.setTiltProfiles(profiles)
        self.logger.info("tilt profiles changed to: %s", profiles)

        # adjust tower profiles
        profiles = self.getTowerProfiles()
        profiles[0][4] = self.towerAdjust['homingFast'][towerSensitivity + 2][0]
        profiles[0][5] = self.towerAdjust['homingFast'][towerSensitivity + 2][1]
        profiles[1][4] = self.towerAdjust['homingSlow'][towerSensitivity + 2][0]
        profiles[1][5] = self.towerAdjust['homingSlow'][towerSensitivity + 2][1]
        self.setTowerProfiles(profiles)
        self.logger.info("tower profiles changed to: %s", profiles)
    #enddef

#endclass
