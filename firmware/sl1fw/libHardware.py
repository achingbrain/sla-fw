# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import logging
from enum import Enum, unique

import serial
import re
from time import sleep
from multiprocessing import Lock
import bitstring
from math import ceil
import pydbus
import os
from collections import deque

from sl1fw.libConfig import HwConfig
from sl1fw.libDebug import Debug
from sl1fw import defines
from sl1fw.tracing_serial import MotionControllerTracingSerial


class MotionControllerException(Exception):
    def __init__(self, message: str, port: MotionControllerTracingSerial):
        self.__serial = port
        super().__init__(f"{message}, trace: {port.trace}")
    #enddef
#endclass


@unique
class MotConComState(Enum):
    UPDATE_FAILED = -3
    COMMUNICATION_FAILED = -2
    WRONG_FIRMWARE = -1
    OK = 0
    APPLICATION_FLASH_CHECKSUM_FAILED = 1
    BOOTLOADER_FLASH_CHECKSUM_FAILED = 2
    SERIAL_NUMBER_CHECK_FAILED = 3
    FUSE_BIT_SETTINGS_FAILED = 4
    BOOT_SECTOR_LOCK_FAILED = 5
    GPIO_SPI_FAILED = 6
    TMC_SPI_FAILED = 7
    TMC_WIRRING_COMMUNICATION_FAILED = 8
    UVLED_FAILED = 9
    UNKNOWN_ERROR = 999

    @classmethod
    def _missing_(cls, value):
        return MotConComState.UNKNOWN_ERROR
    #enddef
#endclass


class MotConComBase:
    MCFWversion = ""
    MCFWrevision = -1
    MCBoardRevision = (-1, -1)
    MCserial = ""

    commOKStr = re.compile('^(.*)ok$')
    commErrStr = re.compile('^e(.)$')
    commErrors = {
        '1': "unspecified failure",
        '2': "busy",
        '3': "syntax error",
        '4': "parameter out of range",
        '5': "operation not permitted",
        '6': "null pointer",
        '7': "command not found",
    }

    _statusBits = {
        'tower': 0,
        'tilt': 1,
        'button': 6,
        'cover': 7,
        'endstop': 8,
        'reset': 13,
        'fans': 14,
        'fatal': 15,
    }

    resetFlags = {
        0: "power-on",
        1: "external",
        2: "brown-out",
        3: "watchdog",
        4: "jtag",
        7: "stack overflow",
    }
#endclass


class MotConCom(MotConComBase):
    def __init__(self, instance_name: str):
        super().__init__()
        self.portLock = Lock()
        self.debug = Debug()
        self.port_trace = deque(maxlen=10)

        self.port = MotionControllerTracingSerial(debug=self.debug)
        self.port.port = defines.motionControlDevice
        self.port.baudrate = 115200
        self.port.bytesize = 8
        self.port.parity = 'N'
        self.port.stopbits = 1
        self.port.timeout = 3.0
        self.port.writeTimeout = 1.0
        self.port.xonxoff = False
        self.port.rtscts = False
        self.port.dsrdtr = False
        self.port.interCharTimeout = None
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


    def connect(self, MCversionCheck: bool) -> MotConComState:
        try:
            state = self.getStateBits(('fatal', 'reset'))
        except MotionControllerException:
            self.logger.exception("Motion controller connect failed")
            return MotConComState.COMMUNICATION_FAILED
        #endif

        if state['fatal']:
            return MotConComState(self.doGetInt("?err"))
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
            return MotConComState.WRONG_FIRMWARE
        else:
            self.logger.info("motion controller firmware version: %s", self.MCFWversion)
        #endif

        tmp = self.doGetIntList("?rev")
        if len(tmp) == 2 and 0 <= divmod(tmp[1], 32)[0] <= 7:
            self.MCFWrevision = tmp[0]
            self.logger.info("motion controller firmware for board revision: %s", self.MCFWrevision)

            self.MCBoardRevision = divmod(tmp[1], 32)
            self.logger.info("motion controller board revision: %d%s", self.MCBoardRevision[1],
                             chr(self.MCBoardRevision[0] + ord('a')))
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

        return MotConComState.OK
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


    def _read_garbage(self) -> None:
        """
        Reads initial garbage found in port. Assumes portlock is already taken
        """
        # TODO: This is not correct, there should be no random garbage around
        while self.port.inWaiting():
            try:
                line = self.port.readline(garbage=True)
                self.logger.debug(f"Garbage pending in MC port: {line}")
            except (serial.SerialException, UnicodeError) as e:
                raise MotionControllerException(f"Failed garbage read", self.port) from e
            #endtry
        #endwhile
    #enddef


    def do(self, cmd, *args, return_process=lambda x: x):
        with self.portLock:
            # Read garbage already pending to be read
            self._read_garbage()

            # Write command
            cmd_string = ' '.join(str(x) for x in (cmd,) + args)
            try:
                self.port.write(f"{cmd_string}\n".encode('ascii'))
            except serial.SerialTimeoutException as e:
                raise MotionControllerException(f"Timeout writing serial port", self.port) from e
            #endtry

            # Read until some response is received
            while True:
                try:
                    line = self.port.read_text_line()
                except Exception as e:
                    raise MotionControllerException("Failed to read line from MC", self.port) from e
                #endtry

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


    def soft_reset(self) -> None:
        with self.portLock:
            try:
                self._read_garbage()
                self.port.mark_reset()
                self.port.write(f"!rst\n".encode('ascii'))
                self._ensure_ready()
            except Exception as e:
                raise MotionControllerException(f"Reset failed", self.port) from e
            #endtry
    #enddef


    def _ensure_ready(self) -> None:
        """
        Ensure MC is ready after reset/flash
        This assumes portLock to be already acquired
        """
        try:
            self.logger.debug(f"\"MCUSR...\" read resulted in: \"{self.port.read_text_line()}\"")
            ready = self.port.read_text_line()
            if ready != "ready":
                self.logger.info(f"\"ready\" read resulted in: \"{ready}\". Sleeping to ensure MC is ready.")
                sleep(1.5)
                self._read_garbage()
            #endif
        except Exception as e:
            raise MotionControllerException("Ready read failed", self.port) from e
        #endtry
    #enddef


    def flash(self, MCBoardVersion):
        import subprocess

        with self.portLock:
            self.reset()

            process = subprocess.Popen(
                [defines.flashMcCommand, defines.dataPath, str(MCBoardVersion), defines.motionControlDevice],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
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

            self._ensure_ready()

            return MotConComState.UPDATE_FAILED if retc else MotConComState.OK
    #enddef


    def reset(self) -> None:
        """
        Does a hard reset of the motion controller.
        Assumes portLock is already acquired
        """
        self.logger.info("Doing hard reset of the motion controller")
        import gpio
        self.port.mark_reset()
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
            raise ValueError(f"State bits count not match! ({bits})")
        #endif

        return {name: bits[self._statusBits[name]] for name in request}
    #enddef

#endclass


class DummyMotConCom(MotConComBase):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.debug = self
        self.port = self
    #enddef

    def getStateBits(self, request=None):
        if not request:
            request = self._statusBits.keys()
        #endif

        return {name: False for name in request}
    #enddef

    def do(self, cmd, *args):
        self.logger.debug(f"mcc.do called while using dummy MotConCom: {cmd} {args}")
    #enddef

    def start(self) -> None:
        pass
    #enddef

    @staticmethod
    def is_open() -> bool:
        return False
    #enddef

    def close(self) -> None:
        pass
    #enddef

    def showItems(self, *args, **kwargs):
        self.logger.debug(f"mcc.debug.showItems called while using dummy MotConCom args: {args}, kwargs: {kwargs}")
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


class Hardware:

    def __init__(self, hwConfig: HwConfig):
        self.logger = logging.getLogger(__name__)
        self.hwConfig = hwConfig

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
        self._tiltEnd = 6016    # top deadlock
        self._tiltMax = self._tiltEnd
        self._tiltCalibStart = 4352
        self._towerMin = -self.hwConfig.calcMicroSteps(155)
        self._towerAboveSurface = -self.hwConfig.calcMicroSteps(145)
        self._towerMax = self.hwConfig.calcMicroSteps(310)
        self._towerEnd = self.hwConfig.calcMicroSteps(150)
        self._towerCalibPos = self.hwConfig.calcMicroSteps(1)
        self._towerResinStartPos = self.hwConfig.calcMicroSteps(36)
        self._towerResinEndPos = self.hwConfig.calcMicroSteps(1)

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


    def connectMC(self, force_flash = False):
        if force_flash:
            state = self.mcc.flash(self.hwConfig.MCBoardVersion)
            if state != MotConComState.OK:
                self.logger.error("Motion controller flash error: %s", state)
                return state
            #endif
        #endif

        state = self.mcc.connect(self.hwConfig.MCversionCheck)
        if state != MotConComState.OK:
            self.logger.error("Motion controller connect error: %s", state)
            return state
        #endif

        if force_flash:
            self.eraseEeprom()
        #endif

        self.initDefaults()

        return state
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


    def flashMC(self):
        self.connectMC(force_flash=True)
    #enddef


    def switchToDummy(self):
        self.mcc = DummyMotConCom()
    #enddef


    def switchToMC(self):
        self.mcc = self.realMcc
        self.connectMC()
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
        return self.mcc.MCBoardRevision[1], (self.mcc.MCBoardRevision[0])
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
        sn = "*INVALID*"
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
                    self.logger.warning("SN checksum FAIL (is %02x:%02x, should be %02x:%02x), getting old SN format" % (scs1, scs2, scsc, scsc ^ 255))
                    sequence_number, is_kit, ean_pn, year, week, origin = sn.unpack('pad:14, uint:17, bool, uint:10, uint:6, pad:2, uint:6, pad:2, uint:4')
                    prefix = "*"
                else:
                    sequence_number, is_kit, ean_pn, year, week, origin = snnew.unpack('pad:4, uint:17, bool, uint:10, uint:6, uint:6, uint:4')
                    prefix = ""
                #endif
                sn = "%s%3sX%02u%02uX%03uX%c%05u" % (prefix, ot.get(origin, "UNK"), week, year, ean_pn, "K" if is_kit else "C", sequence_number)
                self.logger.info(f"SN: {sn}")
            #endif
        except Exception:
            self.logger.exception("CPU serial:")
        #endtry
        return sn, is_kit
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
        self.mcc.soft_reset()  # FIXME MC issue
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


    def beepEcho(self) -> None:
        try:
            self.beep(1800, 0.05)
        except MotionControllerException:
            self.logger.exception("Failed to beep")
        #endtry
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
        if 'fans' not in state:
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
            return {idx: bits[idx] for idx in request}
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
    def getMcTemperatures(self, logTemps = True):
        temps = self.mcc.doGetIntList("?temp", multiply = 0.1)
        if len(temps) != 4:
            raise ValueError(f"TEMPs count not match! ({temps})")
        #endif
        if logTemps:
            self.logger.debug("Temperatures [C]: %s", " ".join(["%.1f" % x for x in temps]))
        #endif
        return temps
    #enddef


    def getUvLedTemperature(self):
        return self.getMcTemperatures(logTemps = False)[self._ledTempIdx]
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
        while homingStatus > 0:  # not done and not error
            homingStatus = self.towerHomingStatus
            sleep(0.1)
        #endwhile
    #enddef


    @property
    def towerHomingStatus(self):
        return self.mcc.doGetInt("?twho")
    #enddef


    def towerSync(self):
        ''' home is at top position '''
        self._towerSynced = False
        self.mcc.do("!twho")
    #enddef


    def isTowerSynced(self):
        ''' return tower status. False if tower is still homing or error occured '''
        if not self._towerSynced:
            if self.towerHomingStatus == 0:
                self.setTowerPosition(self.hwConfig.towerHeight)
                self._towerSynced = True
            else:
                self._towerSynced = False
        #endif
        return self._towerSynced
    #enddef


    @safe_call(False, MotionControllerException)
    def towerSyncWait(self, retries: int = 0):
        ''' blocking method for tower homing. retries = number of additional tries when homing failes '''
        if not self.isTowerMoving():
            self.towerSync()
        #endif

        while True:
            homingStatus = self.towerHomingStatus
            if homingStatus == 0:
                self.setTowerPosition(self.hwConfig.towerHeight)
                self._towerSynced = True
                return True
            elif homingStatus < 0:
                self.logger.warning("Tower homing failed! Status: %d", homingStatus)
                self.mcc.debug.showItems(towerFailed = "homing Fast/Slow")
                if retries < 1:
                    self.logger.error("Tower homing max tries reached!")
                    return False
                else:
                    retries -= 1
                    self.towerSync()
                #endif
            sleep(0.25)
        #endwhile
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


    # TODO use !brk instead. Motor might stall at !mot 0
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
            homingStatus = self.tiltHomingStatus
            sleep(0.1)
        #endwhile
    #enddef


    @property
    def tiltHomingStatus(self):
        return self.mcc.doGetInt("?tiho")
    #enddef


    def tiltSync(self):
        ''' home at bottom position '''
        self._tiltSynced = False
        self.mcc.do("!tiho")
    #enddef


    @safe_call(False, MotionControllerException)
    def isTiltSynced(self):
        ''' return tilt status. False if tilt is still homing or error occured '''
        if not self._tiltSynced:
            if self.tiltHomingStatus == 0:
                self.setTiltPosition(0)
                self._tiltSynced = True
            else:
                self._tiltSynced = False
            #endif
        #endif
        return self._tiltSynced
    #enddef


    @safe_call(False, MotionControllerException)
    def tiltSyncWait(self, retries: int = 0):
        ''' blocking method for tilt homing. retries = number of additional tries when homing failes '''
        if not self.isTiltMoving():
            self.tiltSync()
        #endif

        while True:
            homingStatus = self.tiltHomingStatus
            if homingStatus == 0:
                self.setTiltPosition(0)
                self._tiltSynced = True
                return True
            elif homingStatus < 0:
                self.logger.warning("Ttilt homing failed! Status: %d", homingStatus)
                self.mcc.debug.showItems(tiltFailed = "homing Fast/Slow")
                if retries < 1:
                    self.logger.error("Tilt homing max tries reached!")
                    return False
                else:
                    retries -= 1
                    self.tiltSync()
                #endif
            sleep(0.25)
        #endwhile
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
        return self.tiltSyncWait(retries = 1)
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
