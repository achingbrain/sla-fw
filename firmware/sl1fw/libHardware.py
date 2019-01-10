# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018 Prusa Research s.r.o. - www.prusa3d.com

import logging
import serial
import re
from time import time, sleep
from multiprocessing import Lock

from libDebug import Debug

import defines

class Hardware(object):

    def __init__(self, hwConfig, config):
        self.logger = logging.getLogger(__name__)
        self.hwConfig = hwConfig
        self.config = config
        self.MCversion = ""
        self.MCserial = ""
        self.portLock = Lock()
        self.debug = Debug()

        self._tiltSynced = False
        self._towerSynced = False

        self._lastTiltProfile = None
        self._lastTowerProfile = None

        self._fansRequested = 0
        self._tiltToPosition = 0
        self._towerToPosition = 0

        # (mode, speed)
        self._powerLedStates= { 'normal' : (2, 3), 'warn' : (3, 16), 'error' : (3, 48) }

        self._tiltProfiles = {
                'homingFast'    : 0,
                'homingSlow'    : 1,
                'moveFast'      : 2,
                'moveSlow'      : 3,
                'layer'         : 4,
                'hold'          : 5,
                'release'       : 6,
                'calibration'   : 7,
                }
        self._towerProfiles = {
                'homingFast'    : 0,
                'homingSlow'    : 1,
                'moveFast'      : 2,
                'moveSlow'      : 3,
                'layer'         : 4,
                'hold'          : 5,
                'release'       : 6,
                'resinSensor'   : 7,
                }
        # get sorted profiles names
        self._tiltProfileNames = map(lambda x: x[0], sorted(self._tiltProfiles.items(), key=lambda kv: kv[1]))
        self._towerProfileNames = map(lambda x: x[0], sorted(self._towerProfiles.items(), key=lambda kv: kv[1]))

        self._tiltMin = -3210        # whole turn
        self._tiltMax = 3210
        self._tiltEnd = 1600
        self._towerMin = -self.hwConfig.calcMicroSteps(155)
        self._towerMax = self.hwConfig.calcMicroSteps(310)
        self.towerEnd = self.hwConfig.calcMicroSteps(150)
        self.towerCalibPos = self.hwConfig.calcMicroSteps(2)
        self._towerResinStartPos = self.hwConfig.calcMicroSteps(36)
        self._towerResinEndPos = self.hwConfig.calcMicroSteps(1)
        self._towerResinMin = self.hwConfig.calcMicroSteps(3.75) # cca 50 ml
        self._towerResinMax = self.hwConfig.calcMicroSteps(16)  # cca 200 ml

        self.port = serial.Serial(port = defines.motionControlDevice,
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

        # fan status
        self.current_milli_time = lambda: int(round(time() * 1000)) # FIXME WTF?
        self.coolDownCounter = 0

        self.commOKStr = re.compile('^(.*)ok$')
        self.commErrStr = re.compile('^e(.)$')
        self.commErrors = {
                '1' : "unspecified failure",
                '2' : "busy",
                '3' : "syntax error",
                '4' : "parameter out of range",
                '5' : "operation not permitted",
                }

        self._firmwareCheck()

        self.motorsRelease()
        self.setFansPwm((self.hwConfig.fan1Pwm, self.hwConfig.fan2Pwm, self.hwConfig.fan3Pwm, self.hwConfig.fan4Pwm))
        self.setFans({ 0 : True, 1 : True, 2 : True, 3 : True })
        #self.setFans({ 0 : False, 1 : False, 2 : False, 3 : False })  # all off
        self.setUvLedPwm(self.hwConfig.uvLedPwm)
        self.setPowerLedPwm(self.hwConfig.pwrLedPwm)
        self.resinSensor(False)
    #enddef


    def _intOrNone(self, string):
        try:
            return int(string)
        except Exception:
            return None
        #endtry
    #enddef


    def _commMC(self, *args):

        self.portLock.acquire()

        while self.port.inWaiting():
            try:
                self.logger.info("extra line '%s'", self.port.readline().strip().decode("ascii").encode())
            except Exception:
                self.logger.exception("exception:")
            #endtry
        #endwhile

        params = " ".join(str(x) for x in args)
        self.logger.debug("write '%s'", params)
        self.debug.log("> %s" % params)

        try:
            self.port.write('%s\n' % params)

            while True:
                line = self.port.readline().strip().decode("ascii").encode()
                self.logger.debug("read '%s'", line)
                self.debug.log("< %s" % line)

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
                    self.logger.debug("debug: '%s'", line)
                #endif
            #endwhile

        except Exception:
            self.logger.exception("exception:")
            return None
        finally:
            self.portLock.release()
        #endtry
    #enddef


    def _firmwareCheck(self):
        self.MCversion = self._commMC("?ver")
        if self.hwConfig.MCversionCheck and (self.MCversion is None or self.MCversion != defines.reqMcVersion):
            self.logger.warning("Wrong MC firmware version, flash forced.")

            if not self._flashMC():
                self.logger.critical("Forced flash failed!")
                raise Exception("MC flash failed!")
            #endif

            self.MCversion = self._commMC("?ver")
            if self.MCversion is None or self.MCversion != defines.reqMcVersion:
                self.logger.critical("Wrong MC firmware!")
                raise Exception("Wrong MC firmware!")
            #endif

        else:
            self.logger.info("MC fw version: %s", self.MCversion)
        #endif

        self.MCserial = self._commMC("?ser")
        if self.MCserial:
            self.logger.info("MC serial number: %s", self.MCserial)
        #endif
    #enddef


    def flashMC(self):
        self._flashMC()
        self._firmwareCheck()
    #enddef


    def _flashMC(self):
        import subprocess

        self.portLock.acquire()
        self.resetMc()

        process = subprocess.Popen([defines.flashMcCommand, defines.dataPath, defines.motionControlDevice], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
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


    def getControllerVersion(self):
        return self.MCversion
    #enddef


    def getControllerSerial(self):
        return self.MCserial
    #enddef


    def resetMc(self):
        import gpio
        gpio.setup(131, gpio.OUT)
        gpio.set(131, 1)
        sleep(1/1000000)
        gpio.set(131, 0)
    #enddef


    def eraseEeprom(self):
        self._commMC("!eecl")
        self._commMC("!rst")    # FIXME MC issue
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
                profData = self._commMC(getProfileDataCmd, profId).split(" ")
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
            self._commMC(setProfileCmd, profId)
            self._commMC(setProfileDataCmd, *profiles[profId])
        #endfor
    #enddef


    def setTiltTempProfile(self, profileData):
        return self.setTempProfile(profileData, "!tics", "!ticf")
    #enddef


    def setTowerTempProfile(self, profileData):
        return self.setTempProfile(profileData, "!twcs", "!twcf")
    #enddef


    def setTempProfile(self, profileData, setProfileCmd, setProfileDataCmd):
        self._commMC(setProfileCmd, -1)
        self._commMC(setProfileDataCmd, *profileData)
    #enddef


    def getStallguardBuffer(self):
        samplesList = list()
        samplesCount = self._intOrNone(self._commMC("?sgbc"))
        while samplesCount:
            samples = self._commMC("?sgbd")
            try:
                for val in map(lambda x: int(x, 16), samples.split(" ")):
                    samplesList.append(val)
                    samplesCount -= 1
                #endfor
            except Exception:
                self.logger.exception("exception:")
                break
            #endtry
        #endwhile
        return samplesList
    #enddef


    def beep(self, frequency, lenght):
        self._commMC("!beep", frequency, int(lenght * 1000))
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
        self._commMC("!pled", value)
    #enddef


    def getPowerLedMode(self):
        return self._intOrNone(self._commMC("?pled"))
    #enddef


    def setPowerLedPwm(self, pwm):
        self._commMC("!ppwm", pwm / 5)
    #enddef


    def getPowerLedPwm(self):
        pwm = self._commMC("?ppwm")
        try:
            return int(pwm) * 5
        except Exception:
            return -1
        #endtry
    #enddef


    def setPowerLedSpeed(self, speed):
        self._commMC("!pspd", speed)
    #enddef


    def getPowerLedSpeed(self):
        return self._intOrNone(self._commMC("?pspd"))
    #enddef


    def shutdown(self):
        self._commMC("!shdn", 5)
    #enddef


    def uvLed(self, state):
        self._commMC("!uled", 1 if state else 0)
    #enddef


    def getUvLedState(self):
        return self._commMC("?uled") == "1"
    #enddef


    def setUvLedPwm(self, pwm):
        self._commMC("!upwm", int(pwm * 2.5))
    #enddef


    def getUvLedPwm(self):
        pwm = self._commMC("?upwm")
        try:
            return int(pwm) / 2.5
        except Exception:
            return -1
        #endtry
    #enddef


    def getUvLedVoltages(self):
        retval = list(("0", "0", "0"))
        volts = self._commMC("?volt")
        try:
            i = 0
            for val in map(lambda x: int(x), volts.split(" ")):
                retval[i] = str(val / 1000.0)
                i += 1
            #endfor
        except Exception:
            pass
        #endtry
        return retval
    #enddef


    def cameraLed(self, state):
        self._commMC("!cled", 1 if state else 0)
    #enddef


    def getCameraLedState(self):
        return self._commMC("?cled") == "1"
    #enddef


    def resinSensor(self, state):
        self._commMC("!rsen", 1 if state else 0)
    #enddef


    def getResinSensor(self):
        return self._commMC("?rsen") == "1"
    #enddef


    def getCoverState(self):
        return self._commMC("?covs") == "1"
    #enddef


    def setFans(self, fans):
        for fan, state in fans.iteritems():
            if state:
                self._fansRequested |= 1 << fan
            else:
                self._fansRequested &= ~(1 << fan)
            #endif
        #endfor
        self._commMC("!fans", self._fansRequested)
    #enddef


    def getFans(self):
        retVal = list((False, False, False, False))
        state = self._commMC("?fans")
        try:
            binState = int(state)
            for i in xrange(4):
                retVal[i] = True if binState & (1 << i) else False
            #endfor
        except Exception:
            pass
        #endtry
        return retVal
    #enddef


    def getFanState(self):
        if not self._fansRequested:
            return True
        #endif
        state = self._commMC("?fans")
        try:
            return int(state) & self._fansRequested
        except Exception:
            return False
        #endtry
    #enddef


    def setFansPwm(self, pwms):
        self._commMC("!fpwm", " ".join(map(lambda x: str(x / 5), pwms)))
    #enddef


    def getFansPwm(self):
        retval = list((0, 0, 0, 0))
        pwms = self._commMC("?fpwm")
        try:
            i = 0
            for val in map(lambda x: int(x), pwms.split(" ")):
                retval[i] = val * 5
                i += 1
            #endfor
        except Exception:
            pass
        #endtry
        return retval
    #enddef


    def getFansRpm(self):
        retval = list(("0", "0", "0", "0"))
        rpms = self._commMC("?frpm")
        try:
            i = 0
            for val in map(lambda x: int(x), rpms.split(" ")):
                retval[i] = str(val * 10)
                i += 1
            #endfor
        except Exception:
            pass
        #endtry
        return retval
    #enddef


    def getTemperatures(self):
        retval = list(("-273.15", "-273.15", "-273.15", "-273.15"))
        temps = self._commMC("?temp")
        try:
            i = 0
            for val in map(lambda x: int(x), temps.split(" ")):
                retval[i] = str(val / 10.0)
                i += 1
            #endfor
        except Exception:
            pass
        #endtry
        return retval
    #enddef


    def getTemperatureSystem(self):
        temp = self._commMC("?tems")
        try:
            return int(temp) / 100.0
        except Exception:
            return -273.15
        #endtry
    #enddef


    def getTemperatureUVLED(self):
        temp = self._commMC("?temu")
        try:
            return int(temp) / 100.0
        except Exception:
            return -273.15
        #endtry
    #enddef


    # --- motors ---


    def motorsRelease(self):
        self._commMC("!motr")
        self._tiltSynced = False
        self._towerSynced = False
    #enddef


    # --- tower ---


    def towerSync(self, retries = 2):
        ''' home is at top position, retries = None is infinity '''
        self._towerSyncRetries = retries
        self.setTowerProfile('homingFast')
        self._commMC("!twho")
    #enddef


    def isTowerSynced(self):
        homingStatus = self._intOrNone(self._commMC("?twho"))
        if homingStatus > 0:    # not done and not error
            return False
        elif not homingStatus:
            self.setTowerPosition(self.hwConfig.towerHeight)
            self._towerSynced = True
            return True
        else:
            self.logger.warning("Tower homing failed!")
            self.beepAlarm(3)
            self.debug.showItems(towerFailed = "homing Fast/Slow")
            if self._towerSyncRetries is None or self._towerSyncRetries:
                if self._towerSyncRetries:
                    self._towerSyncRetries -= 1
                #endif
                self.setTowerProfile('homingFast')
                self._commMC("!twho")
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
        self._commMC("!twma", position)
    #enddef


    def towerToPosition(self, mm):
        self.towerMoveAbsolute(self.hwConfig.calcMicroSteps(mm))
    #enddef


    def towerStop(self):
        self._commMC("!mot 0")
    #enddef


    def isTowerMoving(self):
        return self._commMC("?mot") != "0"
    #enddef


    def isTowerOnPosition(self):
        if self.isTowerMoving():
            return False
        #endif
        while self._towerToPosition != self.getTowerPositionMicroSteps():
            self.logger.warning("Tower is not on required position! Sync forced.")
            self.beepAlarm(3)
            self.debug.showItems(towerFailed = self._lastTowerProfile)
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


    def towerZero(self):
        self.towerMoveAbsolute(0)
    #enddef


    def isTowerOnZero(self):
        return self.isTowerOnPosition()
    #enddef


    def setTowerOnMax(self):
        self.setTowerPosition(self.towerEnd)
    #enddef


    def towerTop(self):
        self.towerMoveAbsolute(self.hwConfig.towerHeight)
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
        self._commMC("!twpo", position)
        self.debug.showItems(towerPositon = position)
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
        steps = self._intOrNone(self._commMC("?twpo"))
        self.debug.showItems(towerPositon = steps)
        return steps
    #enddef


    def setTowerProfile(self, profile):
        if profile == self._lastTowerProfile:
            return
        else:
            self._lastTowerProfile = profile
            profileId = self._towerProfiles.get(profile, None)
            if profileId is not None:
                self.debug.showItems(towerProfile = profile)
                self._commMC("!twcs", profileId)
            else:
                self.logger.error("Invalid tower profile '%s'", profile)
            #endif
        #endif
    #enddef


    def getResinVolume(self):
        self.setTowerProfile('moveFast')
        self.towerMoveAbsoluteWait(self._towerResinStartPos) # move quickly to safe distance
        self.resinSensor(True)
        sleep(1)
        self.setTowerProfile('resinSensor')
        self._commMC("!rsme", self._towerResinStartPos - self._towerResinEndPos) # relative movement!
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


    def tiltSyncWait(self, retries = None):
        ''' home at bottom position, retries = None is infinity '''
        while True:
            self.setTiltProfile('homingFast')
            self._commMC("!tiho")
            homingStatus = 1
            while homingStatus > 0: # not done and not error
                homingStatus = self._intOrNone(self._commMC("?tiho"))
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
                self.debug.showItems(tiltFailed = "homing Fast/Slow")
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

                self.setTiltProfile('release')
                self.setTiltPosition(releaseFrom)
                self._commMC("!tima", 800)
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
        self._commMC("!tima", position)
    #enddef


    def tiltStop(self):
        self._commMC("!mot 0")
    #enddef


    def isTiltMoving(self):
        return self._commMC("?mot") != "0"
    #enddef


    def isTiltOnPosition(self):
        if self.isTiltMoving():
            return False
        #endif
        while self._tiltToPosition != self.getTiltPositionMicroSteps():
            self.logger.warning("Tilt is not on required position! Sync forced.")
            self.beepAlarm(3)
            self.debug.showItems(tiltFailed = self._lastTiltProfile)
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


    def setTiltPosition(self, position):
        self._commMC("!tipo", position)
        self.debug.showItems(tiltPosition = position)
    #enddef


    def getTiltPosition(self):
        steps = self.getTiltPositionMicroSteps()
        if steps is None:
            return "ERROR"
        #endif
        return steps
    #enddef


    def getTiltPositionMicroSteps(self):
        steps = self._intOrNone(self._commMC("?tipo"))
        self.debug.showItems(tiltPosition = steps)
        return steps
    #enddef


    def setTiltProfile(self, profile):
        if profile == self._lastTiltProfile:
            return
        else:
            self._lastTiltProfile = profile
            profileId = self._tiltProfiles.get(profile, None)
            if profileId is not None:
                self.debug.showItems(tiltProfile = profile)
                self._commMC("!tics", profileId)
            else:
                self.logger.error("Invalid tilt profile '%s'", profile)
            #endif
        #endif
    #enddef


    # --- generic ---

    def checkFanStatus(self, errorPage, returnPage):
        #self.logger.debug("checkFanStatus started")
        if not self.hwConfig.fanCheck:
            #self.logger.debug("checkFanStatus disable return")
            return
        #endif
        if (self.current_milli_time() - self.coolDownCounter) < ((1000 * 60) * 15):
            #self.logger.debug("checkFanStatus time return")
            return
        #endif
        if not self.getFanState():
            self.coolDownCounter = self.current_milli_time()
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


    def checkTemp(self, errorPage, returnPage, forceFail = False):
        # TODO
        return
        #self.logger.debug("checkTemp started")
        if self.getTemperatureUVLED() < 0:
            if forceFail or not self.hwConfig.fanCheck or not self.getFanState():
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

        if forceFail or self.getTemperatureUVLED() < 80:
            return
        #endif

        self.uvLed(False)
        self.powerLed("error")
        errorPage.show()
        errorPage.showItems(line2 = "OVERHEAT!")
        while(self.getTemperatureUVLED() > 60): # hystereze
            errorPage.showItems(line3 = "Cooling down...")
            self.beepAlarm(3)
            sleep(1)
            errorPage.showItems(line3 = "Temperature is %.1f C" % self.getTemperatureUVLED())
            sleep(1)
        #endwhile

        errorPage.showItems(line2 = "")
        errorPage.showItems(line3 = "")
        returnPage.show()
        self.powerLed("normal")
        self.beepEcho()
        self.uvLed(True)

        #self.logger.debug("checkTemp done")
    #enddef


    def logTemp(self):
        # TODO
        return
        self.logger.info("SYS: %.1f C  LED: %.1f C",
                self.getTemperatureSystem(), self.getTemperatureUVLED())
    #enddef

#endclass
