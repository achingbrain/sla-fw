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

        self._tiltEnabled = 0
        self._towerEnabled = 0

        self._lastTiltProfile = None
        self._lastTowerProfile = None

        self._fansRequested = 0

        self._tiltProfiles = {
                "homingFast"    : 0,
                "homingSlow"    : 1,
                "moveFast"      : 2,
                "moveSlow"      : 3,
                "layer"         : 4,
                "firstLayer"    : 5,
                "reserved1"     : 6,
                "reserved2"     : 7,
                }
        self._towerProfiles = {
                "homingFast"    : 0,
                "homingSlow"    : 1,
                "moveFast"      : 2,
                "moveSlow"      : 3,
                "layer"         : 4,
                "calibration"   : 5,
                "reserved1"     : 6,
                "reserved2"     : 7,
                }
        # get sorted profiles names
        self._tiltProfileNames = map(lambda x: x[0], sorted(self._tiltProfiles.items(), key=lambda kv: kv[1]))
        self._towerProfileNames = map(lambda x: x[0], sorted(self._towerProfiles.items(), key=lambda kv: kv[1]))

        # FIXME spatne hodnoty pro min a mozna i max (opsano z doc)
        # sr0 (starting steprate 0..22000 [steps/s])
        # srm (maximum steprate 0..22000 [steps/s])
        # acc (acceleration 0..800 [256xsteps/s^2])
        # dec (deceleration 0..800 [256xsteps/s^2])
        # cur (current 0..63 [aprox. 1/64A])
        # sgt (stallguard threshold -128..127)
        # cst (coolstep threshold 0..10000 [T])

        #                            960, 1280, 12, 12, 24,  8, 1500
        self.XXX_tiltProfiles = {
                'slowMove' :        (120,  480, 12, 12, 32,  4, 1500),
                'fastMove' :        (960, 1280, 12, 12, 32,  8, 1500),
                'safeSlowMove' :    (120,  480, 12, 12,  8,  2, 1500),
                'safeFastMove' :    (960, 1280, 12, 12,  8,  2, 1500),
                'layer' :           (100,  400, 12, 12, 32,  8, 2000),
                'firstLayer' :      (100,  200, 12, 12, 32,  8, 2000),
                }
        #                            3200, 17600, 250, 250, 34,  6, 1500
        self.XXX_towerProfiles = {
                'slowMove' :        ( 800,  1600, 100, 100, 17,  3, 2000),
                'fastMove' :        (3200, 15000, 250, 250, 30,  4, 1500),
                'safeSlowMove' :    ( 800,  4400, 200, 200, 17,  3, 2000),
                'safeFastMove' :    (3200, 15000, 250, 250, 17,  4, 1500),
                'layer' :           (3200,  9600, 200, 200, 34,  6, 2000),
                'calibration' :     (3200,  4400, 200, 200, 17,  3, 2000),
                }

        self._tiltMin = -3210        # whole turn
        self._tiltMax = 3210
        self._tiltEnd = 1600
        self._towerMin = -self.hwConfig.calcMicroSteps(155)
        self._towerMax = self.hwConfig.calcMicroSteps(310)
        self._towerEnd = self.hwConfig.calcMicroSteps(150)

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
                "1" : "unspecified failure",
                "2" : "busy",
                "3" : "syntax error",
                "4" : "parameter out of range",
                "5" : "operation not permitted",
                }

        self._firmwareCheck()

        self.motorsRelease()
        self.fans(True, True, True, True)  # all on - safety
    #enddef


    def _commMC(self, *args):

        self.portLock.acquire()

        if self.port.inWaiting():
            self.logger.warning("data on serial line: '%s'", self.port.read(256))
        #endif

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
        if self.MCversion is None or self.MCversion != defines.reqMcVersion:
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
        import gpio

        self.portLock.acquire()

        # RESET MC
        gpio.setup(131, gpio.OUT)
        gpio.set(131, 1)
        sleep(1/1000000)
        gpio.set(131, 0)

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
            self.logger.error("%s failed with code %d", defines.hostnameCommand, retc)
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


    def getTiltProfilesNames(self):
        self.logger.debug(str(self._tiltProfileNames))
        return self._tiltProfileNames
    #enddef


    def getTowerProfilesNames(self):
        self.logger.debug(str(self._towerProfileNames))
        return self._towerProfileNames
    #enddef


    def getTiltProfiles(self):
        return self.getProfiles("!tics", "?ticf")
    #enddef


    def getTowerProfiles(self):
        return self.getProfiles("!twcs", "?twcf")
    #enddef


    def getProfiles(self, setProfileCmd, getProfileDataCmd):
        profiles = []
        for profId in xrange(8):
            try:
                self._commMC(setProfileCmd, profId)
                profData = self._commMC(getProfileDataCmd).split(" ")
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
        self._commMC("!pled", 1 if state == "normal" else 0)
    #enddef


    def getPowerLedState(self):
        return self._commMC("?pled") == "1"
    #enddef


    def shutdown(self):
        #self._commMC("!shdn", 5)
        self._commMC("!shdn", 12)
    #enddef


    def uvLed(self, state):
        self._commMC("!uled", 1 if state else 0)
    #enddef


    def getUvLedState(self):
        return self._commMC("?uled") == "1"
    #enddef


    def cameraLed(self, state):
        self._commMC("!cled", 1 if state else 0)
    #enddef


    def getCameraLedState(self):
        return self._commMC("?cled") == "1"
    #enddef


    def getCoverState(self):
        return self._commMC("?covs") == "1"
    #enddef


    def fans(self, *fans):
        self._fansRequested = 0
        for i in xrange(len(fans)):
            self._fansRequested += pow(2, i) if fans[i] else 0
        #endfor
        self.logger.debug("fans: '%s' '%s'", self._fansRequested, fans)
        self._commMC("!fans", self._fansRequested)
    #enddef


    def getFans(self):
        state = self._commMC("?fans")
        try:
            binState = int(state)
            retVal = ()
            for i in xrange(4):
                retVal += (True,) if binState & (1 << i) else (False,)
            #endfor
            return retVal
        except Exception:
            return (False, False, False, False)
        #endtry
    #enddef


    def getFanState(self):
        state = self._commMC("?fans")
        try:
            return int(state) & self._fansRequested
        except Exception:
            return False
        #endtry
    #enddef


    def getRPMs(self):
        retval = list((0, 0, 0, 0))
        rpms = self._commMC("?frpm")
        try:
            i = 0
            for val in map(lambda x: int(x), rpms.split(" ")):
                retval[i] = val
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
        self._tiltEnabled = 0
        self._towerEnabled = 0
    #enddef


    # --- tower ---

    # TODO smazat az bude implementovano v MC
    def _towerHold(self):
        if not self._towerEnabled:
            self._towerEnabled = 1
            self._commMC("!ena", self._tiltEnabled + self._towerEnabled)
        #enddef
    #enddef


    def towerSync(self):
        self._towerHold()
        # home is at top position
        self.setTowerProfile('homingFast')
        self._commMC("!twho")
    #enddef


    def isTowerSynced(self):
        if self._commMC("?twho") == "0":
            self._towerSynced = True
            self._commMC("!twpo", self.hwConfig.towerHeight)
            return True
        else:
            return False
        #endif
    #enddef


    def towerMoveAbsoluteWait(self, position):
        self.towerMoveAbsolute(position)
        while not self.isTowerOnPosition():
            sleep(0.1)
        #endwhile
    #enddef


    def towerMoveAbsolute(self, position):
        self._towerHold()
        self._commMC("!twma", position)
    #enddef


    def towerToPosition(self, mm):
        self.towerMoveAbsolute(self.hwConfig.calcMicroSteps(mm))
    #enddef


    def towerStop(self):
        self._commMC("!mot 0")
    #enddef


    def isTowerOnPosition(self):
        return self._commMC("?mot") == "0"
    #enddef


    def towerZero(self):
        self.towerMoveAbsolute(0)
    #enddef


    def isTowerOnZero(self):
        return self.isTowerOnPosition()
    #enddef


    def setTowerZero(self):
        self._commMC("!twpo", 0)
    #enddef


    def towerTop(self):
        self.towerMoveAbsolute(self.hwConfig.towerHeight)
    #enddef


    def isTowerOnTop(self):
        return self.isTowerOnPosition()
    #enddef


    def towerToMax(self):
        self.towerMoveAbsolute(self._towerMax)
    #enddef


    def isTowerOnMax(self):
        onPosition = self.isTowerOnPosition()
        if onPosition:
            self._commMC("!twpo", self._towerEnd)
        #endif
        return onPosition
    #enddef


    def towerToMin(self):
        self.towerMoveAbsolute(self._towerMin)
    #enddef


    def isTowerOnMin(self):
        onPosition = self.isTowerOnPosition()
        if onPosition:
            self._commMC("!twpo", 0)
        #endif
        return onPosition
    #enddef


    def getTowerPosition(self):
        steps = self._commMC("?twpo")
        self.debug.showItems(towerPositon = steps)
        try:
            return "%.3f mm" % self.hwConfig.calcMM(int(steps))
        except Exception:
            return "ERROR"
        #endtry
    #enddef


    def getTowerPositionMicroSteps(self):
        steps = self._commMC("?twpo")
        self.debug.showItems(towerPositon = steps)
        try:
            return int(steps)
        except Exception:
            return None
        #endtry
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


    # --- tilt ---

    # TODO smazat az bude implementovano v MC
    def _tiltHold(self):
        if not self._tiltEnabled:
            self._tiltEnabled = 2
            self._commMC("!ena", self._tiltEnabled + self._towerEnabled)
        #enddef
    #enddef


    def tiltSyncWait(self):
        ''' home at bottom position '''
        self._tiltHold()
        self.setTiltProfile('homingFast')
        self._commMC("!tiho")
        while self._commMC("?tiho") != "0":
            sleep(0.1)
        #endwhile
        self._commMC("!tipo", 0)
        self._tiltSynced = True
    #enddef


    def tiltMoveAbsolute(self, position):
        self._tiltHold()
        self._commMC("!tima", position)
    #enddef


    def tiltStop(self):
        self._commMC("!mot 0")
    #enddef


    def isTiltOnPosition(self):
        return self._commMC("?mot") == "0"
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
        sleep(0.5)  # FIXME MC issue
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
        onPosition = self.isTiltOnPosition()
        if onPosition:
            self._commMC("!tipo", self._tiltEnd)
        #endif
        return onPosition
    #enddef


    def tiltToMin(self):
        self.tiltMoveAbsolute(self._tiltMin)
    #enddef


    def isTiltOnMin(self):
        onPosition = self.isTiltOnPosition()
        if onPosition:
            self._commMC("!tipo", 0)
        #endif
        return onPosition
    #enddef


    def getTiltPosition(self):
        steps = self._commMC("?tipo")
        self.debug.showItems(tiltPosition = steps)
        if steps is None:
            return "ERROR"
        #endif
        return steps
    #enddef


    def getTiltPositionMicroSteps(self):
        steps = self._commMC("?tipo")
        self.debug.showItems(tiltPosition = steps)
        try:
            return int(steps)
        except Exception:
            return None
        #endtry
    #enddef


    def tiltReset(self):
        if not self._tiltSynced:
            self.tiltSyncWait()
        #endif
        self.setTiltProfile('layer')
        self.tiltDownWait()
        self.tiltUpWait()
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
