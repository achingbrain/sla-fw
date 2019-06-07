# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import logging
import serial
import re
from time import time, sleep
from multiprocessing import Lock
import bitstring
from math import ceil
import pydbus
import os

from sl1fw.libDebug import Debug

from sl1fw import defines


class MotConCom(object):
    MCversion = ""
    MCrevision = ""
    MCserial = ""

    commOKStr = re.compile('^(.*)ok$')
    commErrStr = re.compile('^e(.)$')
    commErrors = {
            '1' : "unspecified failure",
            '2' : "busy",
            '3' : "syntax error",
            '4' : "parameter out of range",
            '5' : "operation not permitted",
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


    def __init__(self, instance_name, serial_port = None, debug = None):
        self.portLock = Lock()
        if debug:
            self.debug = debug
        else:
            self.debug = Debug()
        #endif
        
        if serial_port:
            self.port = serial_port
        else:
            self.port = serial.Serial(port=defines.motionControlDevice,
                                     baudrate=115200,
                                     bytesize=8,
                                     parity='N',
                                     stopbits=1,
                                     timeout=1.0,
                                     writeTimeout=1.0,
                                     xonxoff=False,
                                     rtscts=False,
                                     dsrdtr=False,
                                     interCharTimeout=None)
        #endif

        super(MotConCom, self).__init__()
        self.logger = logging.getLogger(instance_name)
    #enddef


    def __del__(self):
        self.exit()
    #enddef


    def exit(self):
        self.debug.exit()
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
            resetBits = self.doGetBoolList(bitCount = 8, args = ("?rst",))
            bit = 0
            for val in resetBits:
                if val:
                    self.logger.info("motion controller reset flag: %s", self.resetFlags.get(bit, "unknown"))
                #endif
                bit += 1
            #endfor
        #endif

        self.MCversion = self.do("?ver")
        if MCversionCheck and self.MCversion != defines.reqMcVersion:
            return _("Wrong motion controller firmware version")
        else:
            self.logger.info("motion controller firmware version: %s", self.MCversion)
        #endif

        self.MCrevision = self.do("?rev")
        if self.MCrevision:
            self.logger.info("motion controller board revision: %s", self.MCrevision)
        #endif

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
        try:
            return int(self.do(*args))
        except Exception:
            self.logger.exception("exception:")
            return None
        #endtry
    #enddef


    def doGetIntList(self, base = 10, multiply = 1, args = ()):
        try:
            return list(map(lambda x: int(x, base) * multiply, self.do(*args).split(" ")))
        except Exception:
            self.logger.exception("exception:")
            return None
        #endtry
    #enddef


    def doGetBool(self, *args):
        try:
            return self.do(*args) == "1"
        except Exception:
            self.logger.exception("exception:")
            return None
        #endtry
    #enddef


    def doGetBoolList(self, bitCount, args = ()):
        bits = list()
        try:
            num = int(self.do(*args))
            for i in range(bitCount):
                bits.append(True if num & (1 << i) else False)
            #endfor
            return bits
        except Exception:
            self.logger.exception("exception:")
            return None
        #endtry
    #enddef


    def doGetHexedString(self, *args):
        try:
            # TODO: Check this is working ok. This was ported to python 3 but not actually used anywhere to check.
            return bytes.fromhex(self.do(*args)).decode('ascii')
        except Exception:
            self.logger.exception("exception:")
            return None
        #endtry
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


    def do(self, *args):
        if "noSyslog" in args:
            syslog = False
        else:
            syslog = True
        #endif
        self.portLock.acquire()
        while self.port.inWaiting():
            try:
                msg = "| %s" % self.port.readline().strip().decode("ascii").encode()
                if syslog:
                    self.logger.debug(msg)
                #endif
                self.debug.log(msg)
            except Exception:
                self.logger.exception("exception:")
            #endtry
        #endwhile

        params = " ".join(str(x) for x in args if x != "noSyslog")
        msg = "> %s" % params
        if syslog:
            self.logger.debug(msg)
        #endif
        self.debug.log(msg)

        try:
            self.port.write(str('%s\n' % params).encode('ascii'))

            while True:
                try:
                    line = self.port.readline().strip().decode("ascii")
                except:
                    line = ""
                msg = "< %s" % line
                if syslog:
                    self.logger.debug(msg)
                #endif
                self.debug.log(msg)

                if line == '':
                    return None
                #endif

                match = self.commOKStr.match(line)

                if match is not None:
                    return match.group(1).strip() if match.group(1) else True
                #endif

                match = self.commErrStr.match(line)
                if match is not None:
                    err = self.commErrors.get(match.group(1), "unknown error")
                    self.logger.error("error: '%s'", err)
                    return None
                else:
                    msg = "| %s" % line
                    if syslog:
                        self.logger.debug(msg)
                    #endif
                    self.debug.log(msg)
                #endif
            #endwhile

        except Exception:
            self.logger.exception("exception:")
            return None
        finally:
            self.portLock.release()
        #endtry
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
        bits = self.doGetBoolList(bitCount = 16, args = ("?", "noSyslog"))
        if not bits or len(bits) != 16:
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


class dummyMotConCom(object):

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def getStateBits(self, request = None):
        if not request:
            request = self._statusBits.keys()
        #endif
        retval = {}
        for name in request:
            retval[name] = False
        #endfor
        return retval
    #enddef

    def do(self, *args):
        self.logger.debug("do called %s", ','.join([str(x) for x in args]))
    #enddef

#endclass


class Hardware(object):

    def __init__(self, hwConfig, config, serial_port = None, debug = None):
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
        self._tiltProfileNames = list(map(lambda x: x[0], sorted(self._tiltProfiles.items(), key=lambda kv: kv[1])))
        self._towerProfileNames = list(map(lambda x: x[0], sorted(self._towerProfiles.items(), key=lambda kv: kv[1])))

        self._tiltAdjust = {
            'homingFast': [[20,5],[20,6],[20,7],[21,9],[22,12]],
            'homingSlow': [[16,3],[16,5],[16,7],[16,9],[16,11]]
        }

        self._towerAdjust = {
            'homingFast': [[22,0],[22,2],[22,4],[22,6],[22,8]],
            'homingSlow': [[14,0],[15,0],[16,1],[16,3],[16,5]]
        }

        self._fansNames = {
                0 : _("UV LED fan"),
                1 : _("blower fan"),
                2 : _("rear fan"),
                }

        self._sensorsNames = {
                0 : _("UV LED temperature"),
                1 : _("Ambient temperature"),
                }

        self._tiltMin = -12840        # whole turn
        self._tiltMax = 12840
        self._tiltEnd = 5800    #top deadlock
        self._tiltCalibStart = 4300 
        self._towerMin = -self.hwConfig.calcMicroSteps(155)
        self._towerAboveSurface = -self.hwConfig.calcMicroSteps(145)
        self._towerMax = self.hwConfig.calcMicroSteps(310)
        self._towerEnd = self.hwConfig.calcMicroSteps(150)
        self._towerCalibPos = self.hwConfig.calcMicroSteps(1)
        self._towerResinStartPos = self.hwConfig.calcMicroSteps(36)
        self._towerResinEndPos = self.hwConfig.calcMicroSteps(1)

        self.mcc = MotConCom("MC_Main", serial_port=serial_port, debug=debug)
        self.realMcc = self.mcc
        self.cpuSerial = self.readCpuSerial()
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

            waitPage.fill(
                    line1 = _("Updating motion controller firmware."),
                    line2 = _("Please wait..."))
            waitPage.show()

            if not self.mcc.flash(self.hwConfig.MCBoardVersion):
                self.ahojBabi(waitPage, _("Motion controller update has failed!"))
            #endif

            errorMessage = self.mcc.connect(self.hwConfig.MCversionCheck)
            if errorMessage:
                self.logger.error("motion controller error: %s", errorMessage)
                self.ahojBabi(waitPage, errorMessage)
            #endif

            waitPage.showItems(line1 = _("Erasing EEPROM."))
            self.eraseEeprom()

            returnPage.show()
        #endif

        self.initDefaults()
    #enddef


    def initDefaults(self):
        self.motorsRelease()
        self.setFansPwm((self.hwConfig.fan1Pwm, self.hwConfig.fan2Pwm, self.hwConfig.fan3Pwm))
        self.setUvLedCurrent(self.hwConfig.uvCurrent)
        self.setPowerLedPwm(self.hwConfig.pwrLedPwm)
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
        waitPage.fill(
                line1 = _("Forced update of the motion controller firmware."),
                line2 = _("Please wait..."))
        waitPage.show()
        self.mcc.flash(self.hwConfig.MCBoardVersion)
        self.connectMC(waitPage, returnPage)
    #enddef


    def switchToDummy(self):
        self.mcc = dummyMotConCom()
    #enddef


    def switchToMC(self, page_systemwait, actualPage):
        self.mcc = self.realMcc
        self.connectMC(page_systemwait, actualPage)
    #enddef


    @property
    def mcVersion(self):
        return self.mcc.MCversion
    #enddef


    @property
    def mcSerialNo(self):
        return self.mcc.MCserial
    #enddef


    @property
    def cpuSerialNo(self):
        return self.cpuSerial
    #enddef


    @property
    def mcRevision(self):
        return self.mcc.MCrevision
    #enddef


    def readCpuSerial(self):
        ot = { 0 : "CZP" }
        serial = "*INVALID*"
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
        return serial
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
        self.mcc.do("!rst")    # FIXME MC issue
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
                profiles.append(list(map(lambda x: int(x), profData)))
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
            samples = self.mcc.doGetIntList(base = 16, args = ("?sgbd",))
            if samples:
                samplesCount -= len(samples)
                samplesList.extend(samples)
            else:
                self.logger.warning("Values count not match! (%s)", str(samples))
                break
            #endif
        #endwhile
        return samplesList
    #enddef


    def beep(self, frequency, lenght):
        if not self.hwConfig.mute:
            self.mcc.do("!beep", frequency, int(lenght * 1000), "noSyslog")
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
        self.powerLedMode(mode)
        self.setPowerLedSpeed(speed)
    #enddef


    def powerLedMode(self, value):
        self.mcc.do("!pled", value)
    #enddef


    def getPowerLedMode(self):
        return self.mcc.doGetInt("?pled")
    #enddef


    def setPowerLedPwm(self, pwm):
        self.mcc.do("!ppwm", int(pwm / 5))
    #enddef


    def getPowerLedPwm(self):
        pwm = self.mcc.do("?ppwm")
        try:
            return int(pwm) * 5
        except Exception:
            return -1
        #endtry
    #enddef


    def setPowerLedSpeed(self, speed):
        self.mcc.do("!pspd", speed)
    #enddef


    def getPowerLedSpeed(self):
        return self.mcc.doGetInt("?pspd")
    #enddef


    def shutdown(self):
        self.mcc.do("!shdn", 5)
    #enddef


    def uvLed(self, state, time = 0):
        self.mcc.do("!uled", 1 if state else 0, int(time))        
    #enddef


    def getUvLedState(self):
        uvData = self.mcc.doGetIntList(args = ("?uled", "noSyslog"))
        if uvData and 0 < len(uvData) < 3:
            return uvData if len(uvData) == 2 else list((uvData[0], 0))
        else:
            self.logger.warning("UV data count not match! (%s)", str(uvData))
            return list((0, 0))
        #endif
    #enddef


    def setUvLedCurrent(self, current):
        self.mcc.do("!upwm", int(round(current / 3.2)))
    #enddef


    def getUvLedCurrent(self):
        raw = self.mcc.do("?upwm")
        try:
            return int(raw) * 3.2
        except Exception:
            return -1
        #endtry
    #enddef


    def getUvStatistics(self):
        uvData = self.mcc.doGetIntList(args = ("?usta",)) #time counter [s] #TODO add uv average current, uv average temperature
        if uvData and len(uvData) == 1:
            return uvData
        else:
            self.logger.warning("UV statistics data count not match! (%s)", str(uvData))
            return list((0,))
        #endif
    #enddef


    def saveUvStatistics(self):
        self.mcc.do("!usta", 0)
    #enddef


    def clearUvStatistics(self):    # call if UV led was replaced
        self.mcc.do("!usta", 1)
    #enddef


    def getVoltages(self):
        volts = self.mcc.doGetIntList(multiply = 0.001, args = ("?volt",))
        if volts and len(volts) == 4:
            return volts
        else:
            self.logger.warning("Volts count not match! (%s)", str(volts))
            return list((0, 0, 0, 0))
        #endif
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


    def isCoverClosed(self):
        return self.checkState('cover')
    #enddef


    def getPowerswitchState(self):
        return self.checkState('button')
    #enddef


    def checkState(self, name):
        state = self.mcc.getStateBits((name,))
        if state:
            return state[name]
        else:
            self.logger.warning("State check of '%s' has failed", name)
            return False
        #endif
    #enddef


    def startFans(self):
        self.setFans((True, True, True))
        # user can change speed of rear fan to 0 so we don't want to check it
        self.setFanCheckMask((True, True, False))
    #enddef


    def stopFans(self):
        self.setFans((False, False, False))
        self.setFanCheckMask((False, False, False))
    #enddef


    def setFans(self, fans):
        self.mcc.doSetBoolList("!fans", fans)
    #enddef


    def getFans(self):
        fans = self.mcc.doGetBoolList(bitCount = 3, args = ("?fans",))
        if fans and len(fans) == 3:
            return fans
        else:
            self.logger.warning("Fans bits count not match! (%s)", str(fans))
            return list((False, False, False))
        #endif
    #enddef


    def setFanCheckMask(self, mask):
        self.mcc.doSetBoolList("!fmsk", mask)
    #enddef


    def getFanCheckMask(self):
        fans = self.mcc.doGetBoolList(bitCount = 3, args = ("?fmsk",))
        if fans and len(fans) == 3:
            return fans
        else:
            self.logger.warning("Fans check bits count not match! (%s)", str(fans))
            return list((False, False, False))
        #endif
    #enddef


    def getFansError(self):
        state = self.mcc.getStateBits(('fans',))
        if not state:
            self.logger.warning("State check of fans has failed")
        elif not state['fans']:
            return (False, False, False)
        #endif

        fans = self.mcc.doGetBoolList(bitCount = 3, args = ("?fane",))
        if fans and len(fans) == 3:
            return fans
        else:
            self.logger.warning("Fans error bits count not match! (%s)", str(fans))
            return (True, True, True)
        #endif
    #enddef


    def setFansPwm(self, pwms):
        self.mcc.do("!fpwm", " ".join(map(lambda x: str(int(x / 5)), pwms)), 0) # FIXME remove 0 after done in MC
    #enddef


    def getFansPwm(self):
        pwms = self.mcc.doGetIntList(multiply = 5, args = ("?fpwm",))
        if pwms and len(pwms) == 4:  # FIXME 3 after done in MC
            return pwms[0:3]
        else:
            self.logger.warning("PWMs count not match! (%s)", str(pwms))
            return list((0, 0, 0))
        #endif
    #enddef


    def getFansRpm(self):
        rpms = self.mcc.doGetIntList(multiply = 10, args = ("?frpm",))
        if rpms and len(rpms) == 4: # FIXME 3 after done in MC
            return rpms[0:3]
        else:
            self.logger.warning("RPMs count not match! (%s)", str(rpms))
            return list((0, 0, 0))
        #endif
    #enddef


    def getFanName(self, fanNumber):
        return self._fansNames.get(fanNumber, _("unknown fan"))
    #enddef


    def getMcTemperatures(self):
        temps = self.mcc.doGetIntList(multiply = 0.1, args = ("?temp", "noSyslog"))
        if temps and len(temps) == 4:
            self.logger.info("Temperatures [C]: %s", " ".join(map(lambda x: str(x), temps)))
            return temps
        else:
            self.logger.warning("TEMPs count not match! (%s)", str(temps))
            return list((-273.2, -273.2, -273.2, -273.2))
        #endif
    #enddef


    def getUvLedTemperature(self):
        return self.getMcTemperatures()[self._ledTempIdx]
    #endif


    def getSensorName(self, sensorNumber):
        return self._sensorsNames.get(sensorNumber, _("unknown sensor"))
    #enddef


    def getCpuTemperature(self):
        temp = -273.2
        try:
            with open(defines.cpuTempFile, "r") as f:
                temp = round((int(f.read()) / 1000.0), 1)
            #endwith
        except Exception:
            self.logger.exception("CPU temperatures exception:")
        #endtry
        return temp
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
        self.setTowerProfile('homingFast')
        self.mcc.do("!twhc")
        homingStatus = 1
        while homingStatus > 0: # not done and not error
            homingStatus = self.mcc.doGetInt("?twho", "noSyslog")
            sleep(0.1)
        #endwhile
    #enddef


    def towerSync(self, retries = 2):
        ''' home is at top position, retries = None is infinity '''
        self._towerSyncRetries = retries
        self.setTowerProfile('homingFast')
        self.mcc.do("!twho")
    #enddef


    def isTowerSynced(self):
        homingStatus = self.mcc.doGetInt("?twho", "noSyslog")
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
                self.setTowerProfile('homingFast')
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
            pass
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
        if self.mcc.doGetInt("?mot", "noSyslog") & 1:
            return True
        #endif
        return False
    #enddef


    def isTowerOnPosition(self):
        if self.isTowerMoving():
            return False
        #endif
        while self._towerToPosition != self.getTowerPositionMicroSteps():
            self.logger.warning("Tower is not on required position! Sync forced.")
            self.mcc.debug.showItems(towerFailed = self._lastTowerProfile)
            profileBackup = self._lastTowerProfile
            self.towerSyncWait()
            self.setTowerProfile(profileBackup)
            self.towerMoveAbsolute(self._towerToPosition)
            while self.isTowerMoving():
                sleep(0.1)
            #endwhile
        #endwhile

        return True
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


    def setTowerPosition(self, position):
        self.mcc.do("!twpo", position)
        self.mcc.debug.showItems(towerPositon = position)
    #enddef


    def getTowerPosition(self):
        steps = self.getTowerPositionMicroSteps()
        try:
            return "%.3f mm" % self.hwConfig.calcMM(int(steps))
        except Exception:
            return "ERROR"
        #endtry
    #enddef


    def getTowerPositionMicroSteps(self):
        steps = self.mcc.doGetInt("?twpo")
        self.mcc.debug.showItems(towerPositon = steps)
        return steps
    #enddef


    def setTowerProfile(self, profile):
        self._lastTowerProfile = profile
        profileId = self._towerProfiles.get(profile, None)
        if profileId is not None:
            self.mcc.debug.showItems(towerProfile = profile)
            self.mcc.do("!twcs", profileId)
        else:
            self.logger.error("Invalid tower profile '%s'", profile)
        #endif
    #enddef


    def setTowerCurrent(self, current):
        if 0 <= current <= 63:
            self.mcc.do("!twcu", current)
        else:
            self.logger.error("Invalid tower current %d", current)
        #endif
    #enddef


    #  5.0 mm -  35 % -  68.5 ml
    # 10.0 mm -  70 % - 137.0 ml
    # 14.5 mm - 100 % - 200.0 ml

    # 35 % -  70 % : 1.0 mm = 13.7 ml
    # 70 % - 100 % : 0.9 mm = 12.5 ml

    def getResinVolume(self):
        self.setTowerProfile('moveFast')
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
        if not position or position == self._towerResinEndPos:
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
        self.setTiltProfile('homingFast')
        self.mcc.do("!tihc")
        homingStatus = 1
        while homingStatus > 0: # not done and not error
            homingStatus = self.mcc.doGetInt("?tiho", "noSyslog")
            sleep(0.1)
        #endwhile
    #enddef


    def tiltSync(self, retries = None):
        ''' home at bottom position, retries = None is infinity '''
        self._tiltSyncRetries = retries
        self.setTiltProfile('homingFast')
        self.mcc.do("!tiho")
    #enddef


    def isTiltSynced(self):
        homingStatus = self.mcc.doGetInt("?tiho", "noSyslog")
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
                self.setTiltProfile('homingFast')
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
            pass
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
        if self.mcc.doGetInt("?mot", "noSyslog") & 2:
            return True
        #endif
        return False
    #enddef


    def isTiltOnPosition(self):
        if self.isTiltMoving():
            return False
        #endif
        while self._tiltToPosition != self.getTiltPositionMicroSteps():
            self.logger.warning("Tilt is not on required position! Sync forced.")
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
        self.tiltMoveAbsolute(self.getTiltPositionMicroSteps() - tiltProfile[1])
        while self.isTiltMoving():
            sleep(0.1)
        #endwhile
        self.setTiltProfile(self._tiltProfileNames[tiltProfile[3]])
        sleep(tiltProfile[2] / 1000.0)

        # next movement may be splited
        movePerCycle = int(self.getTiltPositionMicroSteps() / tiltProfile[4])
        for i in range(1, tiltProfile[4]):
            self.tiltMoveAbsolute(self.getTiltPositionMicroSteps() - movePerCycle)
            while self.isTiltMoving():
                sleep(0.1)
            #endwhile
            sleep(tiltProfile[5] / 1000.0)
        #endfor

        # ensure we end up at defined bottom position
        self.tiltDownWait()

        # check if tilt is on endstop
        if self.checkState('endstop'):
            return True
        #endif

        # unstuck
        self.logger.warning("Tilt unstucking...")
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
        self.setTiltProfile('homingFast')
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
        self.tiltMoveAbsolute(self.hwConfig.tiltHeight)
        while self.isTiltMoving():
            sleep(0.1)
        #endwhile

        #finish move may be also splited in multiple sections
        movePerCycle = int((self.getTiltPositionMicroSteps() - self.hwConfig.tiltHeight) / self.hwConfig.tuneTilt[2][4])
        for i in range(1, self.hwConfig.tuneTilt[2][4]):
            self.logger.debug("tilt up cycle %d", i)
            self.tiltMoveAbsolute(self.getTiltPositionMicroSteps() - movePerCycle)
            while self.isTiltMoving():
                sleep(0.1)
            #endwhile
            sleep(self.hwConfig.tuneTilt[2][5] / 1000.0)
        #endfor
        self.tiltMoveAbsolute(self.hwConfig.tiltHeight)
        while self.isTiltMoving():
            sleep(0.1)
        #endwhile

        #reduce tilt current to prevent overheat
        self.setTiltCurrent(defines.tiltHoldCurrent)
    #enddef


    def setTiltPosition(self, position):
        self.mcc.do("!tipo", position)
        self.mcc.debug.showItems(tiltPosition = position)
    #enddef


    def getTiltPosition(self):
        steps = self.getTiltPositionMicroSteps()
        if steps is None:
            return "ERROR"
        #endif
        return steps
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


    def setTiltCurrent(self, current):
        if 0 <= current <= 63:
            self.mcc.do("!ticu", current)
        else:
            self.logger.error("Invalid tilt current %d", current)
        #endif
    #enddef


    def stirResin(self):
        for i in range(self.hwConfig.stirringMoves):
            self.setTiltProfile('moveFast')
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

#endclass
