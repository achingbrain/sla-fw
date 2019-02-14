# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import logging
import serial
import re
from time import time, sleep
from multiprocessing import Lock

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

        self.MCserial = self.doGetHexedString("?ser")
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
        self.portLock.acquire()
        while self.port.inWaiting():
            try:
                msg = "| %s" % self.port.readline().strip().decode("ascii").encode()
                self.logger.debug(msg)
                self.debug.log(msg)
            except Exception:
                self.logger.exception("exception:")
            #endtry
        #endwhile

        params = " ".join(str(x) for x in args)
        msg = "> %s" % params
        self.logger.debug(msg)
        self.debug.log(msg)

        try:
            self.port.write('%s\n' % params)

            while True:
                line = self.port.readline().strip().decode("ascii").encode()
                msg = "< %s" % line
                self.logger.debug(msg)
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
                    self.logger.debug(msg)
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
                'layerMove'     : 4,
                'layerRelease'  : 5,
                '<reserved1>'   : 6,
                '<reserved2>'   : 7,
                }
        self._towerProfiles = {
                'homingFast'    : 0,
                'homingSlow'    : 1,
                'moveFast'      : 2,
                'moveSlow'      : 3,
                'layer'         : 4,
                '<reserved1>'   : 5,
                '<reserved2>'   : 6,
                'resinSensor'   : 7,
                }
        # get sorted profiles names
        self._tiltProfileNames = map(lambda x: x[0], sorted(self._tiltProfiles.items(), key=lambda kv: kv[1]))
        self._towerProfileNames = map(lambda x: x[0], sorted(self._towerProfiles.items(), key=lambda kv: kv[1]))

        self._tiltMin = -12840        # whole turn
        self._tiltMax = 12840
        self._tiltEnd = 5600
        self._tiltReleaseTo = 400
        self._tiltFindProfileMinSteps = 640
        self._tiltFindProfileMaxSteps = 1200
        self._towerMin = -self.hwConfig.calcMicroSteps(155)
        self._towerMax = self.hwConfig.calcMicroSteps(310)
        self.towerEnd = self.hwConfig.calcMicroSteps(150)
        self.towerCalibPos = self.hwConfig.calcMicroSteps(2)
        self._towerResinStartPos = self.hwConfig.calcMicroSteps(36)
        self._towerResinEndPos = self.hwConfig.calcMicroSteps(1)
        self._towerResinMin = self.hwConfig.calcMicroSteps(3.75) # cca 50 ml
        self._towerResinMax = self.hwConfig.calcMicroSteps(16)  # cca 200 ml

        self.mcc = MotConCom("MC_Main")
    #enddef


    def connectMC(self, errorPage, returnPage):

        errorMessage = self.mcc.connect(self.hwConfig.MCversionCheck)
        if errorMessage:
            self.logger.warning("motion controller error: %s", errorMessage)

            errorPage.fill(
                    line1 = "Updating motion controller firmware.",
                    line2 = "Please wait...")
            errorPage.show()

            if not self.mcc.flash(self.hwConfig.MCBoardVersion):
                self.ahojBabi(errorPage, "Motion controller update has failed!")
            #endif

            errorMessage = self.mcc.connect(self.hwConfig.MCversionCheck)
            if errorMessage:
                self.logger.error("motion controller error: %s", errorMessage)
                self.ahojBabi(errorPage, errorMessage)
            #endif

            returnPage.show()
        #endif

        self.motorsRelease()
        self.setFansPwm((self.hwConfig.fan1Pwm, self.hwConfig.fan2Pwm, self.hwConfig.fan3Pwm))
        self.setFans((True, True, True))
        self.setFanCheckMask((True, True, False))   # last fan is broken, don't check it
        self.setUvLedCurrent(self.hwConfig.uvCurrent)
        self.setPowerLedPwm(self.hwConfig.pwrLedPwm)
        self.resinSensor(False)
    #enddef


    def ahojBabi(self, errorPage, message):
        errorPage.show()
        errorPage.showItems(line1 = "Fatal error", line2 = message)
        while True:
            errorPage.showItems(line3 = "Please call service.")
            sleep(1)
            errorPage.showItems(line3 = "")
            sleep(1)
        #endwhile
    #enddef


    def flashMC(self, errorPage, returnPage):
        errorPage.fill(
                line1 = "Forced update of motion controller firmware.",
                line2 = "Please wait...")
        errorPage.show()
        self.mcc.flash(self.hwConfig.MCBoardVersion)
        self.connectMC(errorPage, returnPage)
    #enddef


    def getControllerVersion(self):
        return self.mcc.MCversion
    #enddef


    def getControllerSerial(self):
        return self.mcc.MCserial
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
        if not self.hwConfig.mute:
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
        self.mcc.do("!uled", 1 if state else 0, int(time))
    #enddef


    def getUvLedState(self):
        uvData = self.mcc.doGetIntList(args = ("?uled",))
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


    def getUvLedVoltages(self):
        volts = self.mcc.doGetIntList(multiply = 0.001, args = ("?volt",))
        if volts and len(volts) == 3:
            return volts
        else:
            self.logger.warning("Volts count not match! (%s)", str(volts))
            return list((0, 0, 0))
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


    def getCoverState(self):
        return self.mcc.doGetBool("?covs")
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


    def getTemperatures(self):
        temps = self.mcc.doGetIntList(multiply = 0.1, args = ("?temp",))
        if temps and len(temps) == 4:
            return temps
        else:
            self.logger.warning("TEMPs count not match! (%s)", str(temps))
            return list((-273.15, -273.15, -273.15, -273.15))
        #endif
    #enddef


    # --- motors ---


    def motorsRelease(self):
        self.mcc.do("!motr")
        self._tiltSynced = False
        self._towerSynced = False
    #enddef


    # --- tower ---


    def towerHomeCalibrateWait(self):
        self.setTowerProfile('homingFast')
        self.mcc.do("!twhc")
        homingStatus = 1
        while homingStatus > 0: # not done and not error
            homingStatus = self.mcc.doGetInt("?twho")
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
        homingStatus = self.mcc.doGetInt("?twho")
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


    def towerStop(self):
        self.mcc.do("!mot", 0)
    #enddef


    def isTowerMoving(self):
        if self.mcc.doGetInt("?mot") & 1:
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
        self.setTowerPosition(self.towerEnd)
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
            volume = position * 150 / (self._towerResinMax - self._towerResinMin)
            return int(round(volume / 10.0) * 10)
        #endif
    #enddef


    # --- tilt ---


    def tiltHomeCalibrateWait(self):
        self.setTiltProfile('homingFast')
        self.mcc.do("!tihc")
        homingStatus = 1
        while homingStatus > 0: # not done and not error
            homingStatus = self.mcc.doGetInt("?tiho")
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
                homingStatus = self.mcc.doGetInt("?tiho")
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
                self.mcc.debug.showItems(tiltFailed = "homing Fast/Slow")
                position = self.getTiltPositionMicroSteps()
                if position is None:
                    continue
                elif position > 800:
                    self.logger.info("Tilt is stuck at top position")
                    releaseFrom = 1600
                else:
                    self.logger.info("Tilt is stuck at bottom position")
                    releaseFrom = 0
                #endif

                self.setTiltProfile('layerRelease')
                self.setTiltPosition(releaseFrom)
                self.mcc.do("!tima", 800)
                while self.isTiltMoving():
                    sleep(0.1)
                #endwhile
                if self._tiltToPosition != self.getTiltPositionMicroSteps():
                    self.logger.info("Release failed :-(")
                else:
                    self.logger.info("Release was successful :-)")
                #endif

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
        if self.mcc.doGetInt("?mot") & 2:
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
        if whitePixels > (1440 * 2560) * (self.hwConfig.tuneTilt[0][5] / 100.0):
            self.setTiltProfile(self._tiltProfileNames[self.hwConfig.tuneTilt[0][0]])
            for i in xrange(self.hwConfig.tuneTilt[0][3]):
                self.tiltMoveAbsolute(self.getTiltPositionMicroSteps() - self.hwConfig.tuneTilt[0][1])
                while self.isTiltMoving():
                    sleep(0.1)
                #endwhile
                sleep(self.hwConfig.tuneTilt[0][2] / 1000.0)
            #endfor
            self.setTiltProfile(self._tiltProfileNames[self.hwConfig.tuneTilt[0][4]])
        else:
            self.setTiltProfile(self._tiltProfileNames[self.hwConfig.tuneTilt[1][0]])
            self.tiltMoveAbsolute(self.getTiltPositionMicroSteps() - self.hwConfig.tuneTilt[1][1])
            while self.isTiltMoving():
                sleep(0.1)
            #endwhile
            sleep(self.hwConfig.tuneTilt[1][2] / 1000.0)
            self.setTiltProfile(self._tiltProfileNames[self.hwConfig.tuneTilt[1][4]])
        #endif
        self.tiltMoveAbsolute(self._tiltReleaseTo)
        while self.isTiltMoving():
            sleep(0.1)
        #endwhile
        self.tiltLayerCheckPosition()
        self.setTiltCurrent(defines.tiltHoldCurrent)
    #enddef


    def tiltLayerUpWait(self):
        self.setTiltProfile(self._tiltProfileNames[self.hwConfig.tuneTilt[2][4]])
        self.tiltMoveAbsolute(self.hwConfig.tiltHeight - self.hwConfig.tuneTilt[2][1])
        while self.isTiltMoving():
            sleep(0.1)
        #endwhile
        sleep(self.hwConfig.tuneTilt[2][2] / 1000.0)
        self.setTiltProfile(self._tiltProfileNames[self.hwConfig.tuneTilt[2][0]])
        self.tiltUp()
        while self.isTiltMoving():
            sleep(0.1)
        #endwhile
        self.tiltLayerCheckPosition()
        self.setTiltCurrent(defines.tiltHoldCurrent)
    #enddef


    def tiltLayerCheckPosition(self):
        if self._tiltToPosition != self.getTiltPositionMicroSteps():
            self.logger.warning("Forcing release. Target pos: %d, actual pos: %d", self._tiltToPosition, self.getTiltPositionMicroSteps())
            self.beepAlarm(3)
            self.setTiltProfile('layerRelease')
            #simulate another release movement
            for i in xrange(3):
                self.tiltMoveAbsolute(self.getTiltPositionMicroSteps() - 200)
                while self.isTiltMoving():
                    sleep(0.1)
                #endwhile
                sleep(1)
            #endfor
            for i in xrange(3):
                if not self.tiltSyncWait():
                    self.setTiltPosition(800)
                    self.setTiltProfile('layerRelease')
                    self.tiltMoveAbsolute(0)
                    while self.isTiltMoving():
                        sleep(0.1)
                    #endwhile
                else:
                    return
                #endif
            #endfor
            self.logger.error("Printer is stuck. Shutting down")
            self.shutdown()
        #endif
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


    def checkFanStatus(self, errorPage, returnPage):
        #self.logger.debug("checkFanStatus started")
        if not self.hwConfig.fanCheck:
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

            errorPage.show()
            errorPage.showItems(line3 = "Please call service.")
            while(counter < 10):
                errorPage.showItems(line2 = "FAN ERROR!")
                self.beepAlarm(3)
                counter += 1
                sleep(1)
                errorPage.showItems(line2 = "")
                sleep(1)
            #endwhile
            errorPage.showItems(line2 = "")
            errorPage.showItems(line3 = "")
            returnPage.show()
            self.powerLed("normal")
        else:
            self._fanFailed = False
        #endif
        #self.logger.debug("checkFanStatus done")
    #enddef


    def checkCoverStatus(self, errorPage, returnPage):
        #self.logger.debug("checkCoverStatus started")
        if not self.hwConfig.coverCheck:
            #self.logger.debug("checkCoverStatus disable return")
            return
        #endif
        if not self.getCoverState():
            #self.logger.debug("checkCoverStatus stateOK return")
            return
        #endif
        self.powerLed("warn")
        errorPage.show()
        errorPage.showItems(line3 = "to continue!")
        pocet = 0
        while self.getCoverState():
            errorPage.showItems(line2 = "Close cover")
            pocet -= 1
            if pocet < 0:
                pocet = 5
                self.beepAlarm(3)
            #endif
            sleep(1)
            errorPage.showItems(line2 = "")
            sleep(1)
        #endwhile
        errorPage.showItems(line2 = "")
        errorPage.showItems(line3 = "")
        returnPage.show()
        self.powerLed("normal")
        #self.logger.debug("checkCoverStatus done")
    #enddef


    def logTemp(self, temps):
        self.logger.info("Temperatures [C]: %s", " ".join(map(lambda x: str(x), temps)))
    #enddef


    def checkTemp(self, errorPage, returnPage, forceFail = False):
        #self.logger.debug("checkTemp started")
        temps = self.getTemperatures()
        self.logTemp(temps)
        temp = temps[self._ledTempIdx]
        if temp < 0:
            if forceFail or not self.hwConfig.fanCheck or self.getFansError():
                self.uvLed(False)
                self.logger.critical("EMERGENCY STOP - LED temperature")
                self.powerLed("error")
                errorPage.show()
                errorPage.showItems(line2 = "Emergency stop!")
                errorPage.showItems(line3 = "Please call service.")
                while True:
                    errorPage.showItems(line1 = "LED temperature sensor failure!")
                    self.beepAlarm(3)
                    sleep(1)
                    errorPage.showItems(line1 = "")
                    sleep(1)
                #endwhile
            else:
                self.logger.warning("LED temperature has not been read correctly!")
            #endif
        #endif

        if forceFail or temp < 60:
            return
        #endif

        self.uvLed(False)
        self.powerLed("error")
        errorPage.show()
        errorPage.showItems(line2 = "OVERHEAT!")
        while(temp > 40): # hystereze
            errorPage.showItems(line3 = "Cooling down...")
            self.beepAlarm(3)
            sleep(1)
            errorPage.showItems(line3 = "Temperature is %.1f C" % temp)
            sleep(1)
            temps = self.getTemperatures()
            self.logTemp(temps)
            temp = temps[self._ledTempIdx]
        #endwhile

        errorPage.showItems(line2 = "")
        errorPage.showItems(line3 = "")
        returnPage.show()
        self.powerLed("normal")
        self.beepEcho()
        self.uvLed(True)

        #self.logger.debug("checkTemp done")
    #enddef


    def findTiltProfile(self, profileNo, skipStep, defaultPos, threshold, currMin, currMax, sgtMin, sgtMax):
        tiltProfiles = self.getTiltProfiles()
        profileDef = tiltProfiles[self._tiltProfiles["homingFast"]] #use default homingFast profile for undone movements
        profileTmp = tiltProfiles[profileNo]
        self.setTiltTempProfile(profileDef)
        self.setTiltPosition(self._tiltMax)
        self.tiltDown()
        while self.isTiltMoving():
            sleep(0.1)
        #endwhile

        for current in xrange(currMin, currMax):
            profileTmp[4] = current
            for sgThreshold in xrange(sgtMin, sgtMax):
                profileTmp[5] = sgThreshold
                result = self.tryProfile( profileDef, profileTmp, skipStep, defaultPos, threshold)
                if result == 0:
                    for i in xrange(10):
                        resultTry = self.tryProfile(profileDef, profileTmp, skipStep, defaultPos, threshold)
                        self.logger.debug("try %d. Profile: %s, result: %d", i, profileTmp, resultTry)
                        if resultTry != 0:
                            break
                        #endif
                    #endfor
                    if resultTry == -2:    #try next current
                        break
                    #endif
                    if i == 9:
                        tiltProfiles[profileNo] = profileTmp
                        self.setTiltProfiles(tiltProfiles)
                        return profileTmp
                    #endif
                elif result == -2:
                    break
                #endif
            #endfor
        #endfor
    #enddef


    def tryProfile(self, profileDef, profileTmp, skipStep, defaultPos, threshold):
        self.setTiltTempProfile(profileDef)
        self.setTiltPosition(0)
        self.tiltMoveAbsolute(defaultPos)
        while self.isTiltMoving():
            sleep(0.25)
        #endwhile

        self.setTiltTempProfile(profileTmp)
        self.mcc.do("!sgbd")   #reset buffer
        self.setTiltPosition(defaultPos + 1200)
        self.tiltDown()
        while self.isTiltMoving():
            sleep(0.1)
        #endwhile
        position = self.getTiltPositionMicroSteps()
        stepsCheck = False
        if skipStep:
            if (position > self._tiltFindProfileMinSteps) and (position < self._tiltFindProfileMaxSteps):
                stepsCheck = True
            #endif
        else:
            if (position >= self._tiltFindProfileMaxSteps - 256) and (position <= self._tiltFindProfileMaxSteps):
                stepsCheck = True
            #endif
        #endif
        if stepsCheck:
            sgData = self.getStallguardBuffer()
            del sgData[:5]
            average = (sum(sgData[:-5]) * 1.0) / (len(sgData[:-5]) * 1.0)
            variance = sum([(xi - average) ** 2.0 for xi in sgData[:-5]]) / (len(sgData[:-5]) - 1)
            stdev = variance ** (1 / 2.0)
            sgDataTail = sgData[-5:]
            self.logger.debug("data %s", sgData)
            if skipStep:
                minCount = sum(value < (average - 5 * stdev) for value in sgDataTail)
                if average > threshold:
                    if 0 < minCount < 4:
                        return 0 #profile OK
                    #endif
                #endif
            else:
                minCount = sum(value < (average - 2 * stdev) for value in sgDataTail)
                if average > threshold:
                    if minCount == 0:
                        return 0 #profile OK
                    #endif
                #endif
            #endif
        #endif
        self.setTiltTempProfile(profileDef)
        self.setTiltPosition(position)
        self.tiltDown()
        while self.isTiltMoving():
            sleep(0.1)
        #endwhile
        if (position < 800):
            return -2 #try next current. SGT too insensitive
        #endif
        return -1 #try next sgt. SGT too sensitive
    #enddef

#endclass
