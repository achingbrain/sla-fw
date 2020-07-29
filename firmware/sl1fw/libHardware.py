# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# TODO: Fix following pylint problems
# pylint: disable=no-else-return
# pylint: disable=too-many-lines
# pylint: disable=too-few-public-methods
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-locals
# pylint: disable=too-many-public-methods


import logging
import os
import re
from math import ceil
from time import sleep

import bitstring
import pydbus

from sl1fw import defines
from sl1fw.errors.errors import TiltHomeFailure, TowerHomeFailure
from sl1fw.libConfig import HwConfig
from sl1fw.motion_controller.controller import MotionController
from sl1fw.motion_controller.states import MotConComState
from sl1fw.errors.exceptions import MotionControllerException


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


class Fan:
    def __init__(self, name, maxRpm, defaultRpm, enabled):
        super().__init__()
        self.name = name
        self.__minRpm = defines.fanMinRPM
        self.__maxRpm = maxRpm
        self.targetRpm = defaultRpm
        self.__enabled = enabled
        # TODO add periodic callback on the background
        # self.__error = False
        # self.__realRpm = 0

    @property
    def targetRpm(self) -> int:
        return self.__targetRpm

    @targetRpm.setter
    def targetRpm(self, val):
        self.__enabled = True
        if val < self.__minRpm :
            self.__targetRpm = self.__minRpm
            self.__enabled = False
        elif val > self.__maxRpm :
            self.__targetRpm = self.__maxRpm
        else:
            self.__targetRpm = val

    @property
    def enabled(self) -> bool:
        return self.__enabled

    # TODO methods to save, load, reset to defaults


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
        self._ambientTempIdx = 1

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

        self.fans = {
            0 : Fan(N_("UV LED fan"), defines.fanMaxRPM[0], self.hwConfig.fan1Rpm, self.hwConfig.fan1Enabled),
            1 : Fan(N_("blower fan"), defines.fanMaxRPM[1], self.hwConfig.fan2Rpm, self.hwConfig.fan2Enabled),
            2 : Fan(N_("rear fan"), defines.fanMaxRPM[2], self.hwConfig.fan3Rpm, self.hwConfig.fan3Enabled)
        }

        self._sensorsNames = {
                0 : N_("UV LED temperature"),
                1 : N_("Ambient temperature"),
                2 : N_("<reserved1>"),
                3 : N_("<reserved2>"),
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

        self.mcc = MotionController(defines.motionControlDevice)
        self.boardData = self.readCpuSerial()

        self._tower_moving = False
        self._tilt_moving = False
        self._towerPositionRetries = None
    #enddef


    def start(self):
        self.mcc.start()
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
        self.uvLedPwm = self.hwConfig.uvPwm
        self.powerLedPwm = self.hwConfig.pwrLedPwm
        self.resinSensor(False)
        self.stopFans()
    #enddef


    def flashMC(self):
        self.connectMC(force_flash=True)
    #enddef


    @property
    def tilt_end(self) -> int:
        return self._tiltEnd

    @property
    def tilt_min(self) -> int:
        return self._tiltMin

    @property
    def tilt_calib_start(self) -> int:
        return self._tiltCalibStart

    @property
    def tower_min(self) -> int:
        return self._towerMin

    @property
    def tower_max(self) -> int:
        return self._towerMax

    @property
    def tower_end(self) -> int:
        return self._towerEnd

    @property
    def tower_above_surface(self) -> int:
        return self._towerAboveSurface

    @property
    def tower_calib_pos(self) -> int:
        return self._towerCalibPos

    @property
    def mcFwVersion(self):
        return self.mcc.fw['version']
    #enddef


    @property
    def mcFwRevision(self):
        return self.mcc.fw['revision']
    #enddef


    @property
    def mcBoardRevision(self):
        if self.mcc.board['revision'] > -1 and self.mcc.board['subRevision'] != "":
            return "%d%s" % (self.mcc.board['revision'], self.mcc.board['subRevision'] )
        else:
            return "*INVALID*"
        #endif
    #enddef


    @property
    def mcSerialNo(self):
        return self.mcc.board['serial']
    #enddef


    @property
    def cpuSerialNo(self):
        return self.boardData[0]
    #enddef


    @property
    def isKit(self):
        return self.boardData[1]
    #enddef


    @property
    def is500khz(self):
        return self.mcc.board['revision'] >= 6 and self.mcc.board['subRevision'] == 'c'
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
                self.logger.error("MAC checksum FAIL (is %02x:%02x, should be %02x:%02x)", mcs1, mcs2, mcsc, mcsc ^ 255)
            else:
                mac_hex = ":".join(re.findall("..", mac.hex))
                self.logger.info("MAC: %s (checksum %02x:%02x)", mac_hex, mcs1, mcs2)

                # byte order change
                sn = bitstring.BitArray(length = 64, uintle = snbe)

                scs2, scs1, snnew = sn.unpack('uint:8, uint:8, bits:48')
                scsc = snnew.count(1)
                if scsc != scs1 or scsc ^ 255 != scs2:
                    self.logger.warning("SN checksum FAIL (is %02x:%02x, should be %02x:%02x), getting old SN format", scs1, scs2, scsc, scsc ^ 255)
                    sequence_number, is_kit, ean_pn, year, week, origin = sn.unpack('pad:14, uint:17, bool, uint:10, uint:6, pad:2, uint:6, pad:2, uint:4')
                    prefix = "*"
                else:
                    sequence_number, is_kit, ean_pn, year, week, origin = snnew.unpack('pad:4, uint:17, bool, uint:10, uint:6, uint:6, uint:4')
                    prefix = ""
                #endif
                sn = "%s%3sX%02u%02uX%03uX%c%05u" % (prefix, ot.get(origin, "UNK"), week, year, ean_pn, "K" if is_kit else "C", sequence_number)
                self.logger.info("SN: %s", sn)
            #endif
        except Exception:
            self.logger.exception("CPU serial:")
        #endtry
        return sn, is_kit
    #enddef


    def checkFailedBoot(self):
        """
        Check for failed boot by comparing current and last boot slot

        :return: True is last boot failed, false otherwise
        """
        try:
            # Get slot statuses
            rauc = pydbus.SystemBus().get("de.pengutronix.rauc", "/")["de.pengutronix.rauc.Installer"]
            status = rauc.GetSlotStatus()

            a = "no-data"
            b = "no-data"

            for slot, data in status:
                if slot == "rootfs.0":
                    a = data['boot-status']
                elif slot == "rootfs.1":
                    b = data['boot-status']
                #endif
            #endfor

            self.logger.info("Slot A boot status: %s", a)
            self.logger.info("Slot B boot status: %s", b)

            if a == 'good' and b == 'good':
                # Device is booting fine, remove stamp
                if os.path.isfile(defines.bootFailedStamp):
                    os.remove(defines.bootFailedStamp)
                #endif
                return False
            else:
                self.logger.error("Detected broken boot slot !!!")
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
        except Exception:
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
            except MotionControllerException:
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
        for _ in range(count):
            self.beep(1800, 0.1)
            sleep(0.5)
        #endfor
    #enddef


    def beepAlarm(self, count):
        for _ in range(count):
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
        if uvData and len(uvData) < 3:
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
        self.mcc.do("!upwm", int(pwm))
    #enddef


    @safe_call([0], (MotionControllerException, ValueError))
    def getUvStatistics(self):
        uvData = self.mcc.doGetIntList("?usta")  # time counter [s] #TODO add uv average current, uv average temperature
        if len(uvData) != 2:
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


    def clearDisplayStatistics(self): # call if print display was replaced
        self.mcc.do("!usta", 2)
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
        self.setFans(mask = { 0 : True, 1 : True, 2 : True })
    #enddef


    def stopFans(self):
        self.setFans(mask = { 0 : False, 1 : False, 2 : False })
    #enddef


    def setFans(self, mask):
        out = list()
        for key in self.fans:
            if self.fans[key].enabled and mask.get(key):
                out.append(True)
            else:
                out.append(False)
        #endfor
        self.mcc.do("!frpm", " ".join(str(fan.targetRpm) for fan in self.fans.values()))
        self.mcc.doSetBoolList("!fans", out)
    #enddef


    def getFans(self, request = (0, 1, 2)):
        return self.getFansBits("?fans", request)
    #enddef


    @safe_call({ 0: False, 1: False, 2: False }, (MotionControllerException, ValueError))
    def getFansError(self):
        state = self.mcc.getStateBits(['fans'])
        if 'fans' not in state:
            raise ValueError(f"'fans' not in state: {state}")
        #endif
        fansError = self.getFansBits("?fane", (0, 1, 2))
        return fansError
    #enddef


    def getFansBits(self, cmd, request):
        try:
            bits = self.mcc.doGetBoolList(cmd, bit_count= 3)
            if len(bits) != 3:
                raise ValueError(f"Fans bits count not match! {bits}")
            #endif
            return {idx: bits[idx] for idx in request}
        except (MotionControllerException, ValueError):
            self.logger.exception("getFansBits failed")
            return dict.fromkeys(request, False)
        #endtry
    #enddef


    def getFansRpm(self, request = (0, 1, 2)):
        try:
            rpms = self.mcc.doGetIntList("?frpm", multiply = 1)
            if not rpms or len(rpms) != 3:
                raise ValueError(f"RPMs count not match! ({rpms})")
            #endif
            return rpms
        except (MotionControllerException, ValueError):
            self.logger.exception("getFansRpm failed")
            return dict.fromkeys(request, 0)
        #endtry
    #enddef


    @safe_call([-273.2, -273.2, -273.2, -273.2], (MotionControllerException, ValueError))
    def getMcTemperatures(self, logTemps = True):
        temps = self.mcc.doGetIntList("?temp", multiply = 0.1)
        if len(temps) != 4:
            raise ValueError(f"TEMPs count not match! ({temps})")
        #endif
        if logTemps:
            self.logger.info("Temperatures [C]: %s", " ".join(["%.1f" % x for x in temps]))
        #endif
        return temps
    #enddef


    def getUvLedTemperature(self):
        return self.getMcTemperatures(logTemps = False)[self._ledTempIdx]
    #endif

    def getAmbientTemperature(self):
        return self.getMcTemperatures(logTemps = False)[self._ambientTempIdx]
    #endif

    def getSensorName(self, sensorNumber):
        return _(self._sensorsNames.get(sensorNumber, N_("unknown sensor")))
    #enddef


    @safe_call(-273.2, Exception)
    def getCpuTemperature(self): # pylint: disable=no-self-use
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
        """ home is at top position """
        self._towerSynced = False
        self.mcc.do("!twho")
    #enddef


    def isTowerSynced(self):
        """ return tower status. False if tower is still homing or error occured """
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
        """ blocking method for tower homing. retries = number of additional tries when homing failes """
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
        """ check dest. position, retries = None is infinity """
        self._towerPositionRetries = retries
        if self.isTowerMoving():
            return False
        #endif
        while self._towerToPosition != self.getTowerPositionMicroSteps():
            if self._towerPositionRetries is None or self._towerPositionRetries:
                if self._towerPositionRetries:
                    self._towerPositionRetries -= 1
                #endif
                self.logger.warning(
                    "Tower is not on required position! Sync forced. Actual position: %d, Target position: %d ",
                    self.getTowerPositionMicroSteps(), self._towerToPosition)
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
    #enddef


    @safe_call("ERROR", Exception)
    def getTowerPosition(self):
        steps = self.getTowerPositionMicroSteps()
        return "%.3f mm" % self.hwConfig.calcMM(int(steps))
    #enddef


    def getTowerPositionMicroSteps(self):
        steps = self.mcc.doGetInt("?twpo")
        return steps
    #enddef


    @safe_call(None, (ValueError, MotionControllerException))
    def setTowerProfile(self, profile):
        self._lastTowerProfile = profile
        profileId = self._towerProfiles.get(profile, None)
        if profileId is None:
            raise ValueError(f"Invalid tower profile '{profile}'")
        #endif
        self.mcc.do("!twcs", profileId)
    #enddef


    @safe_call(None, (MotionControllerException, ValueError))
    def setTowerCurrent(self, current): # pylint: disable=unused-argument,no-self-use
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
    def get_precise_resin_volume_ml(self):
        self.setTowerProfile('homingFast')
        self.towerMoveAbsoluteWait(self._towerResinStartPos)  # move quickly to safe distance
        self.resinSensor(True)
        sleep(1)
        self.setTowerProfile('resinSensor')
        self.mcc.do("!rsme", self._towerResinStartPos - self._towerResinEndPos)  # relative movement!
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
            return volume
        #endif
    #enddef

    def getResinVolume(self):
        return int(round(self.get_precise_resin_volume_ml() / 10.0) * 10)

    @staticmethod
    def calcPercVolume(volume_ml):
        return 10 * ceil(10 * volume_ml / defines.resinMaxVolume)
    #enddef


    # --- tilt ---


    def tiltHomeCalibrateWait(self):
        self.mcc.do("!tihc")
        homingStatus = 1
        while homingStatus > 0:  # not done and not error
            homingStatus = self.tiltHomingStatus
            sleep(0.1)
        #endwhile
    #enddef


    @property
    def tiltHomingStatus(self):
        return self.mcc.doGetInt("?tiho")
    #enddef


    def tiltSync(self):
        """home at bottom position"""
        self._tiltSynced = False
        self.mcc.do("!tiho")
    #enddef


    @safe_call(False, MotionControllerException)
    def isTiltSynced(self):
        """return tilt status. False if tilt is still homing or error occured"""
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
        """blocking method for tilt homing. retries = number of additional tries when homing fails"""
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
                self.logger.warning("Tilt homing failed! Status: %d", homingStatus)
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
        if self.getTiltPositionMicroSteps() != self._tiltToPosition:
            self.logger.warning(
                "Tilt is not on required position! Sync forced. Actual position: %d, Target position: %d ",
                self.getTiltPositionMicroSteps(), self._tiltToPosition)
            profileBackup = self._lastTiltProfile
            self.tiltSyncWait()
            self.setTiltProfile(profileBackup)
            self.tiltMoveAbsolute(self._tiltToPosition)
            while self.isTiltMoving():
                sleep(0.1)
            #endwhile
            if self.getTiltPositionMicroSteps() != self._tiltToPosition:
                return False
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
        for _ in range(tiltProfile[4]):
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
            if -defines.tiltHomingTolerance <= self.getTiltPositionMicroSteps() <= defines.tiltHomingTolerance:
                return True
            #endif
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
        for _ in range(self.hwConfig.tuneTilt[2][4]):
            self.tiltMoveAbsolute(self.getTiltPositionMicroSteps() + movePerCycle)
            while self.isTiltMoving():
                sleep(0.1)
            #endwhile
            sleep(self.hwConfig.tuneTilt[2][5] / 1000.0)
        #endfor
    #enddef


    def setTiltPosition(self, position):
        self.mcc.do("!tipo", position)
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
        return steps
    #enddef


    def setTiltProfile(self, profile):
        self._lastTiltProfile = profile
        profileId = self._tiltProfiles.get(profile, None)
        if profileId is not None:
            self.mcc.do("!tics", profileId)
        else:
            self.logger.error("Invalid tilt profile '%s'", profile)
        #endif
    #enddef


    @safe_call(None, (MotionControllerException, ValueError))
    def setTiltCurrent(self, current):
        if 0 <= current <= 63:
            self.mcc.do("!ticu", current)
        else:
            self.logger.error("Invalid tilt current %d", current)
        #endif
    #enddef


    def tiltGotoFullstep(self, goUp: int = 0):
        self.mcc.do("!tigf", goUp)
    #enddef


    def stirResin(self):
        for _ in range(self.hwConfig.stirringMoves):
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


    def tower_home(self) -> None:
        """
        Home tower axis
        """
        self.powerLed("warn")
        if not self.towerSyncWait():
            raise TowerHomeFailure()
        self.powerLed("normal")
    #enddef


    def tilt_home(self) -> None:
        """
        Home tilt axis
        """
        self.powerLed("warn")
        # assume tilt is up (there may be error from print)
        self.setTiltPosition(self.tilt_end)
        self.tiltLayerDownWait(True)
        if not self.tiltSyncWait():
            raise TiltHomeFailure()
        self.setTiltProfile("moveFast")
        self.tiltLayerUpWait()
        self.powerLed("normal")
    #enddef


    def tower_move(self, speed: int, set_profiles: bool = True) -> bool:
        """
        Start / stop tower movement

        TODO: This should be checked by heartbeat or the command should have limited ttl

        :param: Movement speed

            :-2: Fast down
            :-1: Slow down
            :0: Stop
            :1: Slow up
            :2: Fast up
        :return: True on success, False otherwise
        """
        if not self._tower_moving and set_profiles:
            self.setTowerProfile('moveSlow' if abs(speed) < 2 else 'homingFast')

        if speed > 0:
            if self._tower_moving:
                if self.isTowerOnMax():
                    return False
            else:
                self._tower_moving = True
                self.towerToMax()
            return True
        elif speed < 0:
            if self._tower_moving:
                if self.isTowerOnMin():
                    return False
            else:
                self._tower_moving = True
                self.towerToMin()
            return True
        self.towerStop()
        self._tower_moving = False
        return True
    #enddef


    def tilt_move(self, speed: int, set_profiles: bool = True) -> bool:
        """
        Start / stop tilt movement

        TODO: This should be checked by heartbeat or the command should have limited ttl

        :param: Movement speed

           :-2: Fast down
           :-1: Slow down
           :0: Stop
           :1: Slow up
           :2: Fast up
        :return: True on success, False otherwise
        """
        if not self._tilt_moving and set_profiles:
            self.setTiltProfile('moveSlow' if abs(speed) < 2 else 'homingFast')

        if speed > 0:
            if self._tilt_moving:
                if self.isTiltOnMax():
                    return False
            else:
                self._tilt_moving = True
                self.tiltToMax()
            return True
        elif speed < 0:
            if self._tilt_moving:
                if self.isTiltOnMin():
                    return False
            else:
                self._tilt_moving = True
                self.tiltToMin()
            return True
        self.tiltStop()
        self._tilt_moving = False
        return True
    #enddef


    @property
    def tower_position_nm(self) -> int:
        """
        Read or set tower position in nm
        """
        # TODO: Raise exception if tower not synced
        microsteps = self.getTowerPositionMicroSteps()
        return self.hwConfig.tower_microsteps_to_nm(microsteps)
    #enddef


    @tower_position_nm.setter
    def tower_position_nm(self, position_nm: int) -> None:
        # TODO: This needs some safety check
        self.towerToPosition(position_nm / 1000 / 1000)
    #enddef


    @property
    def tilt_position(self) -> int:
        """
        Read or set tilt position in micro-steps
        """
        # TODO: Raise exception if tilt not synced
        return self.getTiltPositionMicroSteps()
    #enddef


    @tilt_position.setter
    def tilt_position(self, micro_steps: int):
        # TODO: This needs some safety check
        self.tiltMoveAbsolute(micro_steps)
    #enddef

    def getMeasPwms(self):
        if self.is500khz:
            return defines.uvLedMeasMinPwm500k, defines.uvLedMeasMaxPwm500k
        else:
            return defines.uvLedMeasMinPwm, defines.uvLedMeasMaxPwm
        #endif
    #enddef

    def getMinPwm(self):
        return self.getMeasPwms()[0]
    #enddef

    def getMaxPwm(self):
        return self.getMeasPwms()[1]
    #enddef

#endclass
