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

from libDebug import Debug

import defines


class MotConCom(object):

    portLock = Lock()
    debug = Debug()
    port = serial.Serial(port = defines.motionControlDevice,
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

    selfCheckErrors = {
            1 : "Application flash checksum",
            2 : "Bootloader flash checksum",
            3 : "Serial number check",
            4 : "Fuse bit settings",
            5 : "Boot-section lock",
            6 : "GPIO SPI",
            7 : "TMC SPI",
            8 : "TMC wiring/signals",
            9 : "UV-led",
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
        super(MotConCom, self).__init__()
        self.logger = logging.getLogger(instance_name)
    #enddef


    def connect(self, MCversionCheck):
        stateBits = self.doGetBoolList(bitCount = 16, args = ("?",))
        if not stateBits or len(stateBits) != 16:
            self.logger.error("State bits count not match! (%s)", str(stateBits))
            return "Communication failed"
        #endif

        if stateBits[15]:
            errorCode = self.doGetInt("?err")
            error = "%s has failed!" % self.selfCheckErrors.get(errorCode, "Something unknown")
            return error
        #endif

        if stateBits[13]:
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
            return "Wrong motion controller firmware version"
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
            return map(lambda x: int(x, base) * multiply, self.do(*args).split(" "))
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
            for i in xrange(bitCount):
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
            return self.do(*args).decode("hex")
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
            self.port.write('%s\n' % params)

            while True:
                line = self.port.readline().strip().decode("ascii").encode()
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

#endclass


class dummyMotConCom(object):
    pass
#endclass


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
        self._powerLedStates= { 'normal' : (1, 2), 'warn' : (2, 10), 'error' : (3, 15) }

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
        self._tiltProfileNames = map(lambda x: x[0], sorted(self._tiltProfiles.items(), key=lambda kv: kv[1]))
        self._towerProfileNames = map(lambda x: x[0], sorted(self._towerProfiles.items(), key=lambda kv: kv[1]))

        self._tiltAdjust = {
            'homingFast': [[20,5],[20,6],[20,7],[21,9],[22,12]],
            'homingSlow': [[16,3],[16,5],[16,7],[16,9],[16,11]]
        }

        self._towerAdjust = {
            'homingFast': [[22,0],[22,2],[22,4],[22,6],[22,8]],
            'homingSlow': [[14,0],[15,0],[16,1],[16,3],[16,5]]
        }

        self._tiltMin = -12840        # whole turn
        self._tiltMax = 12840
        self._tiltEnd = 5800    #top deadlock
        self._tiltCalibStart = 4300 
        self._tiltReleaseTo = 400
        self._tiltHomeOffset = 0
        self.tiltRehomeCounter = 3
        self._tiltFindProfileMinSteps = 640
        self._tiltFindProfileMaxSteps = 1200
        self._towerCalibMaxOffset = self.hwConfig.calcMicroSteps(0.3)
        self._towerMin = -self.hwConfig.calcMicroSteps(155)
        self._towerAboveSurface = -self.hwConfig.calcMicroSteps(145)
        self._towerMax = self.hwConfig.calcMicroSteps(310)
        self._towerEnd = self.hwConfig.calcMicroSteps(150)
        self._towerCalibPos = self.hwConfig.calcMicroSteps(1)
        self._towerResinStartPos = self.hwConfig.calcMicroSteps(36)
        self._towerResinEndPos = self.hwConfig.calcMicroSteps(1)

        self._minAmbientTemp = 16.0 # 18 C from manual. Capsule is not calibrated, add some tolerance
        self._maxAmbientTemp = 34.0 # 32 C from manual. Capsule is not calibrated, add some tolerance
        self._maxA64Temp = 70.0
        self._maxUVTemp = 50.0
        self._maxTempDiff = 3.0

        self.mcc = MotConCom("MC_Main")
        self.cpuSerial = self.readCpuSerial()
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

        self.dummyMC = False
        self.initDefaults()
    #enddef


    def initDefaults(self):
        self.motorsRelease()
        self.setFansPwm((self.hwConfig.fan1Pwm, self.hwConfig.fan2Pwm, self.hwConfig.fan3Pwm))
        #TODO remove this awful hack to enable fans only after UV is turned on
        #self.setFans((True, True, True))
        self.setFanCheckMask((True, True, True))
        self.setUvLedCurrent(self.hwConfig.uvCurrent)
        self.setPowerLedPwm(self.hwConfig.pwrLedPwm)
        self.resinSensor(False)
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
                line1 = _("Forced update of motion controller firmware."),
                line2 = _("Please wait..."))
        waitPage.show()
        self.mcc.flash(self.hwConfig.MCBoardVersion)
        self.connectMC(waitPage, returnPage)
    #enddef


    def switchToDummy(self):
        self.mcc = dummyMotConCom()
        self.dummyMC = True
    #enddef


    def switchToMC(self, page_systemwait, actualPage):
        self.mcc = MotConCom("MC_Main")
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
            s = bitstring.BitArray(bytes = open(defines.cpuSNFile, 'rb').read())
            mac, mcs1, mcs2, snbe = s.unpack('pad:192, bits:48, uint:8, uint:8, pad:224, uintbe:64')
            mcsc = mac.count(1)
            if mcsc != mcs1 or mcsc ^ 255 != mcs2:
                self.logger.error("MAC checksum FAIL (is %02x:%02x, should be %02x:%02x)" % (mcs1, mcs2, mcsc, mcsc ^ 255))
            else:
                self.logger.info("MAC: %s (checksum %02x:%02x)", ":".join(map(lambda x: x.encode("hex"), mac.bytes)), mcs1, mcs2)

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


    def eraseEeprom(self):
        self.mcc.do("!eecl")
        self.mcc.do("!rst")    # FIXME MC issue
    #enddef


    def getTiltProfilesNames(self):
        self.logger.debug(str(self._tiltProfileNames))
        return self._tiltProfileNames
    #enddef


    def getTowerProfilesNames(self):
        self.logger.debug(str(self._towerProfileNames))
        return self._towerProfileNames
    #enddef


    def getTiltProfiles(self):
        return self.getProfiles("?ticf")
    #enddef


    def getTowerProfiles(self):
        return self.getProfiles("?twcf")
    #enddef


    def getProfiles(self, getProfileDataCmd):
        profiles = []
        for profId in xrange(8):
            try:
                profData = self.mcc.do(getProfileDataCmd, profId).split(" ")
                profiles.append(map(lambda x: int(x), profData))
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
        for profId in xrange(8):
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
        if not self.hwConfig.mute and not self.dummyMC:
            self.mcc.do("!beep", frequency, int(lenght * 1000))
        #endif
    #enddef


    def beepEcho(self):
        self.beep(1800, 0.05)
    #enddef


    def beepRepeat(self, count):
        for num in xrange(count):
            self.beep(1800, 0.1)
            sleep(0.5)
        #endfor
    #enddef


    def beepAlarm(self, count):
        for num in xrange(count):
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
        self.mcc.do("!ppwm", pwm / 5)
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
        #TODO remove this awful hack to enable fans only after UV is turned on  
        if state == True:
            self.setFans((True, True, True))
        #endif
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
        self.mcc.do("!rsen", 1 if state else 0)
    #enddef


    def getResinSensor(self):
        return self.mcc.doGetBool("?rsen")
    #enddef


    def getResinSensorState(self):
        return self.mcc.doGetBool("?rsst")
    #enddef


    def isCoverClosed(self):
        bits = self.mcc.doGetBoolList(bitCount = 16, args = ("?",))
        if not bits or len(bits) != 16:
            self.logger.warning("State bits count not match! (%s)", str(bits))
            return False
        else:
            return bits[7]
        #endif
    #enddef


    def getPowerswitchState(self):
        bits = self.mcc.doGetBoolList(bitCount = 16, args = ("?",))
        if not bits or len(bits) != 16:
            self.logger.warning("State bits count not match! (%s)", str(bits))
            return False
        else:
            return bits[6]
        #endif
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


    # TODO remove
    def getFansError(self):
        fans = self.mcc.doGetBoolList(bitCount = 3, args = ("?fane",))
        if fans and len(fans) == 3:
            return fans[0] or fans[1] or fans[2]
        else:
            self.logger.warning("Fans error bits count not match! (%s)", str(fans))
            return True
        #endif
    #enddef


    def setFansPwm(self, pwms):
        self.mcc.do("!fpwm", " ".join(map(lambda x: str(x / 5), pwms)), 0) # FIXME remove 0 after done in MC
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


    def getMcTemperatures(self):
        temps = self.mcc.doGetIntList(multiply = 0.1, args = ("?temp",))
        if temps and len(temps) == 4:
            return temps
        else:
            self.logger.warning("TEMPs count not match! (%s)", str(temps))
            return list((-273.2, -273.2, -273.2, -273.2))
        #endif
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
            self.beepAlarm(3)
            self.mcc.debug.showItems(towerFailed = "homing Fast/Slow")
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
            self.beepAlarm(3)
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
        self.towerMoveAbsolute(0)
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


    def tiltSyncWait(self, retries = None):
        ''' home at bottom position, retries = None is infinity '''
        while True:
            self.setTiltProfile('homingFast')
            self.mcc.do("!tiho")
            homingStatus = 1
            while homingStatus > 0: # not done and not error
                homingStatus = self.mcc.doGetInt("?tiho", "noSyslog")
                sleep(0.1)
            #endwhile
            # test homing result
            if not homingStatus:
                self.setTiltPosition(0)
                self._tiltSynced = True
                return True
            else:
                self.logger.warning("Tilt homing failed!")
                self.beepAlarm(3)
                # repeat count, None is infinity
                if retries is None:
                    continue
                elif retries:
                    retries -= 1
                    continue
                else:
                    self.logger.error("Tilt homing max tries reached!")
                    return False
                #endif
            #endif
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
            self.beepAlarm(3)
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


    def tiltLayerDownWait(self, whitePixels = 0):
        #use movement settings according to number of white pixels at actual layer
        if whitePixels > self.hwConfig.whitePixelsThd:
            tiltProfile = self.hwConfig.tuneTilt[0]
        else:
            tiltProfile = self.hwConfig.tuneTilt[1]
        #endif

        #initial release movement with optional sleep at the end
        self.setTiltProfile(self._tiltProfileNames[tiltProfile[0]])
        self.tiltMoveAbsolute(self.getTiltPositionMicroSteps() - tiltProfile[1])
        while self.isTiltMoving():
            sleep(0.1)
        #endwhile
        self.setTiltProfile(self._tiltProfileNames[tiltProfile[3]])
        sleep(tiltProfile[2] / 1000.0)

        #next movement may be split
        movePerCycle = int((self.getTiltPositionMicroSteps() - self._tiltReleaseTo) / tiltProfile[4])
        for i in xrange(1, tiltProfile[4]):
            self.tiltMoveAbsolute(self.getTiltPositionMicroSteps() - movePerCycle)
            while self.isTiltMoving():
                sleep(0.1)
            #endwhile
            sleep(tiltProfile[5] / 1000.0)
        #endfor

        #ensure we end up at defined bottom position
        self.tiltMoveAbsolute(self._tiltReleaseTo)
        while self.isTiltMoving():
            sleep(0.1)
        #endwhile

        #when number of white pixels is bigger than threshold, force tilt home
        position = self.getTiltPositionMicroSteps()
        if whitePixels > self.hwConfig.whitePixelsThd:
            self.logger.warning("Forcing rehome")
            #repeat defined number of times
            for i in xrange(tiltProfile[7]):
                self.logger.debug("rehome and release try %d", i)
                self.setTiltProfile('homingFast')
                if not self.tiltSyncWait(2):    #home 3x
                    #if home fails try to release
                    self.setTiltPosition(2000)
                    self.setTiltProfile("layerMoveSlow")
                    self.tiltMoveAbsolute(0)
                    while self.isTiltMoving():
                        sleep(0.1)
                    #endwhile
                else:
                    self.logger.debug("Succesfully rehomed")
                    return True
                #endif
            #endfor
            self.logger.error("Printer is stuck...")
            return False
        else:
            return True
        #endif
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
        for i in xrange(1, self.hwConfig.tuneTilt[2][4]):
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
            self.mcc.do("?ticf")    # FIXME why?
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
        self.setTiltProfile('moveFast')
        for i in xrange(3):
            self.tiltUpWait()
            self.tiltDownWait()
        #endfor
    #enddef


    # --- generic ---


    def getCurrentMiliTime(self):
        return int(round(time() * 1000))
    #enddef


    def checkFanStatus(self, waitPage, returnPage):
        #self.logger.debug("checkFanStatus started")
        if not self.hwConfig.fanCheck or self.dummyMC:
            #self.logger.debug("checkFanStatus disable return")
            return
        #endif
        if self.getFansError():
            if self._fanFailed and self.getCurrentMiliTime() - self._coolDownCounter < 1000 * 60 * 15:
                #self.logger.debug("checkFanStatus time return")
                return
            #endif
            self._fanFailed = True
            self._coolDownCounter = self.getCurrentMiliTime()
            counter = 0
            self.powerLed("error")

            waitPage.show()
            waitPage.showItems(line3 = _("Please contact tech support!"))
            while(counter < 10):
                waitPage.showItems(line2 = _("FAN ERROR!"))
                self.beepAlarm(3)
                counter += 1
                sleep(1)
                waitPage.showItems(line2 = "")
                sleep(1)
            #endwhile
            waitPage.showItems(line2 = "")
            waitPage.showItems(line3 = "")
            returnPage.show()
            self.powerLed("normal")
        else:
            self._fanFailed = False
        #endif
        #self.logger.debug("checkFanStatus done")
    #enddef


    def checkCoverStatus(self, waitPage, returnPage):
        #self.logger.debug("checkCoverStatus started")
        if not self.hwConfig.coverCheck:
            #self.logger.debug("checkCoverStatus disable return")
            return
        #endif
        if self.isCoverClosed():
            #self.logger.debug("checkCoverStatus stateOK return")
            return
        #endif
        self.powerLed("warn")
        waitPage.show()
        waitPage.showItems(line3 = _("to continue!"))
        pocet = 0
        while not self.isCoverClosed():
            waitPage.showItems(line2 = _("Close cover"))
            pocet -= 1
            if pocet < 0:
                pocet = 5
                self.beepAlarm(3)
            #endif
            sleep(1)
            waitPage.showItems(line2 = "")
            sleep(1)
        #endwhile
        waitPage.showItems(line2 = "")
        waitPage.showItems(line3 = "")
        returnPage.show()
        self.powerLed("normal")
        #self.logger.debug("checkCoverStatus done")
    #enddef


    def logTemp(self, temps):
        self.logger.info("Temperatures [C]: %s", " ".join(map(lambda x: str(x), temps)))
    #enddef


    def checkTemp(self, waitPage, returnPage, forceFail = False):
        #self.logger.debug("checkTemp started")
        if self.dummyMC:
            return
        #endif
        temps = self.getMcTemperatures()
        self.logTemp(temps)
        temp = temps[self._ledTempIdx]
        if temp < 0:
            if forceFail or not self.hwConfig.fanCheck or self.getFansError():
                self.uvLed(False)
                self.logger.critical("EMERGENCY STOP - LED temperature")
                self.powerLed("error")
                waitPage.show()
                waitPage.showItems(line2 = _("Emergency stop!"))
                waitPage.showItems(line3 = _("Please contact tech support!"))
                while True:
                    waitPage.showItems(line1 = _("LED temperature sensor failure!"))
                    self.beepAlarm(3)
                    sleep(1)
                    waitPage.showItems(line1 = "")
                    sleep(1)
                #endwhile
            else:
                self.logger.warning("LED temperature has not been read correctly!")
            #endif
        #endif

        if forceFail or temp < self._maxUVTemp:
            return
        #endif

        self.uvLed(False)
        self.powerLed("error")
        waitPage.show()
        waitPage.showItems(line2 = _("OVERHEAT!"))
        while(temp > self._maxUVTemp - 10): # hystereze
            waitPage.showItems(line3 = _("Cooling down..."))
            self.beepAlarm(3)
            sleep(1)
            waitPage.showItems(line3 = _("Temperature is %.1f C") % temp)
            sleep(1)
            temps = self.getMcTemperatures()
            self.logTemp(temps)
            temp = temps[self._ledTempIdx]
        #endwhile

        waitPage.showItems(line2 = "")
        waitPage.showItems(line3 = "")
        returnPage.show()
        self.powerLed("normal")
        self.beepEcho()
        self.uvLed(True)

        #self.logger.debug("checkTemp done")
    #enddef

#endclass
