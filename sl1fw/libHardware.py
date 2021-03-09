# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# TODO: Fix following pylint problems
# pylint: disable=too-many-lines
# pylint: disable=too-few-public-methods
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-locals
# pylint: disable=too-many-public-methods
# pylint: disable=too-many-statements
# pylint: disable=too-many-branches

import functools
import logging
import os
import re
from math import ceil
from threading import Thread
from time import sleep
from typing import Optional

import bitstring
import pydbus
from PySignal import Signal

from sl1fw import defines
from sl1fw.errors.errors import TiltHomeFailed, TowerHomeFailed, TowerEndstopNotReached, TowerHomeCheckFailed
from sl1fw.errors.exceptions import MotionControllerException
from sl1fw.configs.hw import HwConfig
from sl1fw.motion_controller.controller import MotionController
from sl1fw.motion_controller.states import MotConComState
from sl1fw.utils.value_checker import ValueChecker
from sl1fw.hardware.exposure_screen import ExposureScreen
from sl1fw.hardware.printer_model import PrinterModel


def safe_call(default_value, exceptions):
    """
    Decorate method to be safe to call

    Wraps method call in try-cache block, cache exceptions and in case of troubles log exception and return
    safe default value.

    :param default_value: Value to return if wrapped function fails
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

        return func

    return decor


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
        if val < self.__minRpm:
            self.__targetRpm = self.__minRpm
            self.__enabled = False
        elif val > self.__maxRpm:
            self.__targetRpm = self.__maxRpm
        else:
            self.__targetRpm = val

    @property
    def enabled(self) -> bool:
        return self.__enabled

    # TODO methods to save, load, reset to defaults


class Hardware:
    def __init__(self, hw_config: HwConfig):
        self.logger = logging.getLogger(__name__)
        self.config = hw_config

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
        self._powerLedStates = {"normal": (1, 2), "warn": (2, 10), "error": (3, 15), "off": (3, 64)}

        self._tiltProfiles = {
            "homingFast": 0,
            "homingSlow": 1,
            "moveFast": 2,
            "moveSlow": 3,
            "layerMoveSlow": 4,
            "layerRelease": 5,
            "layerMoveFast": 6,
            "<reserved2>": 7,
        }
        self._towerProfiles = {
            "homingFast": 0,
            "homingSlow": 1,
            "moveFast": 2,
            "moveSlow": 3,
            "layer": 4,
            "layerMove": 5,
            "<reserved2>": 6,
            "resinSensor": 7,
        }

        # get sorted profiles names
        self._tiltProfileNames = [x[0] for x in sorted(list(self._tiltProfiles.items()), key=lambda kv: kv[1])]
        self._towerProfileNames = [x[0] for x in sorted(list(self._towerProfiles.items()), key=lambda kv: kv[1])]

        self.tiltAdjust = {
            #               -2      -1      0     +1     +2
            "homingFast": [[20, 5], [20, 6], [20, 7], [21, 9], [22, 12]],
            "homingSlow": [[16, 3], [16, 5], [16, 7], [16, 9], [16, 11]],
        }

        self.towerAdjust = {
            #               -2      -1      0     +1     +2
            "homingFast": [[22, 0], [22, 2], [22, 4], [22, 6], [22, 8]],
            "homingSlow": [[14, 0], [15, 0], [16, 1], [16, 3], [16, 5]],
        }

        self.fans = {
            0: Fan(N_("UV LED fan"), defines.fanMaxRPM[0], self.config.fan1Rpm, self.config.fan1Enabled),
            1: Fan(N_("blower fan"), defines.fanMaxRPM[1], self.config.fan2Rpm, self.config.fan2Enabled),
            2: Fan(N_("rear fan"), defines.fanMaxRPM[2], self.config.fan3Rpm, self.config.fan3Enabled),
        }

        self._sensorsNames = {
            0: N_("UV LED temperature"),
            1: N_("Ambient temperature"),
            2: N_("<reserved1>"),
            3: N_("<reserved2>"),
        }

        # FIXME why here and not in defines.py?
        self._tiltMin = -12800  # whole turn
        self._tiltEnd = 6016  # top deadlock
        self._tiltMax = self._tiltEnd
        self._tiltCalibStart = 4352
        self._towerMin = -self.config.calcMicroSteps(155)
        self._towerAboveSurface = -self.config.calcMicroSteps(145)
        self._towerMax = self.config.calcMicroSteps(310)
        self._towerEnd = self.config.calcMicroSteps(150)
        self._towerCalibPos = self.config.calcMicroSteps(1)
        self._towerResinStartPos = self.config.calcMicroSteps(36)
        self._towerResinEndPos = self.config.calcMicroSteps(1)

        self.mcc = MotionController(defines.motionControlDevice)
        self.boardData = self.readCpuSerial()
        self._emmc_serial = self._read_emmc_serial()

        self._tower_moving = False
        self._tilt_moving = False
        self._tilt_move_last_position: Optional[int] = None
        self._towerPositionRetries = None

        self._value_refresh_run = True
        self._value_refresh_thread = Thread(daemon=True, target=self._value_refresh_body)

        self.exposure_screen = ExposureScreen()
        self.printer_model = PrinterModel.NONE

        self.fans_changed = Signal()
        self.mc_temps_changed = Signal()
        self.cpu_temp_changed = Signal()
        self.led_voltages_changed = Signal()
        self.resin_sensor_state_changed = Signal()
        self.cover_state_changed = Signal()
        self.power_button_state_changed = Signal()
        self.mc_sw_version_changed = Signal()
        self.uv_statistics_changed = Signal()
        self.tower_position_changed = Signal()
        self.tilt_position_changed = Signal()

        self.mcc.power_button_changed.connect(self.power_button_state_changed.emit)
        self.mcc.cover_state_changed.connect(self.cover_state_changed.emit)
        self.mcc.fans_state_changed.connect(lambda x: self.fans_changed.emit())
        self.mcc.tower_status_changed.connect(lambda x: self.tower_position_changed.emit())
        self.mcc.tilt_status_changed.connect(lambda x: self.tilt_position_changed.emit())

    def start(self):
        self.printer_model = self.exposure_screen.start()
        self.mcc.start()
        self._value_refresh_thread.start()

    def exit(self):
        self._value_refresh_run = False
        self._value_refresh_thread.join()
        self.mcc.exit()
        self.exposure_screen.exit()

    def connectMC(self, force_flash=False):
        if force_flash:
            state = self.mcc.flash(self.config.MCBoardVersion)
            if state != MotConComState.OK:
                self.logger.error("Motion controller flash error: %s", state)
                return state

        state = self.mcc.connect(self.config.MCversionCheck)
        if state != MotConComState.OK:
            self.logger.error("Motion controller connect error: %s", state)
            return state

        if force_flash:
            self.eraseEeprom()

        self.initDefaults()

        self.mc_sw_version_changed.emit()

        return state

    def _value_refresh_body(self):
        checkers = [
            ValueChecker(self.getFansRpm, self.fans_changed, False),
            ValueChecker(functools.partial(self.getMcTemperatures, False), self.mc_temps_changed),
            ValueChecker(self.getCpuTemperature, self.cpu_temp_changed),
            ValueChecker(self.getVoltages, self.led_voltages_changed),
            ValueChecker(self.getResinSensorState, self.resin_sensor_state_changed),
            ValueChecker(self.getUvStatistics, self.uv_statistics_changed),
        ]

        while self._value_refresh_run:
            for checker in checkers:
                checker.check()
                sleep(0.5)

    def initDefaults(self):
        self.motorsRelease()
        self.uvLedPwm = self.config.uvPwm
        self.powerLedPwm = self.config.pwrLedPwm
        self.resinSensor(False)
        self.stopFans()

    def flashMC(self):
        self.connectMC(force_flash=True)

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
    def white_pixels_threshold(self) -> int:
        return self.exposure_screen.parameters.width_px * self.exposure_screen.parameters.height_px * self.config.limit4fast // 100

    @property
    def mcFwVersion(self):
        return self.mcc.fw["version"]

    @property
    def mcFwRevision(self):
        return self.mcc.fw["revision"]

    @property
    def mcBoardRevision(self):
        if self.mcc.board["revision"] > -1 and self.mcc.board["subRevision"] != "":
            return "%d%s" % (self.mcc.board["revision"], self.mcc.board["subRevision"])

        return "*INVALID*"

    @property
    def mcSerialNo(self):
        return self.mcc.board["serial"]

    @property
    def cpuSerialNo(self):
        return self.boardData[0]

    @property
    def isKit(self):
        return self.boardData[1]

    @property
    def emmc_serial(self) -> str:
        return self._emmc_serial

    @property
    def is500khz(self):
        # FIXME this will not work for board "7a"
        return self.mcc.board["revision"] >= 6 and self.mcc.board["subRevision"] == "c"

    def readCpuSerial(self):
        ot = {0: "CZP"}
        sn = "*INVALID*"
        is_kit = True  # kit is more strict
        try:
            with open(defines.cpuSNFile, "rb") as nvmem:
                s = bitstring.BitArray(bytes=nvmem.read())

            # pylint: disable = unbalanced-tuple-unpacking
            # pylint does not understand tuples passed by bitstring
            mac, mcs1, mcs2, snbe = s.unpack("pad:192, bits:48, uint:8, uint:8, pad:224, uintbe:64")
            mcsc = mac.count(1)
            if mcsc != mcs1 or mcsc ^ 255 != mcs2:
                self.logger.error("MAC checksum FAIL (is %02x:%02x, should be %02x:%02x)", mcs1, mcs2, mcsc, mcsc ^ 255)
            else:
                mac_hex = ":".join(re.findall("..", mac.hex))
                self.logger.info("MAC: %s (checksum %02x:%02x)", mac_hex, mcs1, mcs2)

                # byte order change
                # pylint: disable = unbalanced-tuple-unpacking
                # pylint does not understand tuples passed by bitstring
                sn = bitstring.BitArray(length=64, uintle=snbe)

                scs2, scs1, snnew = sn.unpack("uint:8, uint:8, bits:48")
                scsc = snnew.count(1)
                if scsc != scs1 or scsc ^ 255 != scs2:
                    self.logger.warning(
                        "SN checksum FAIL (is %02x:%02x, should be %02x:%02x), getting old SN format",
                        scs1,
                        scs2,
                        scsc,
                        scsc ^ 255,
                    )
                    sequence_number, is_kit, ean_pn, year, week, origin = sn.unpack(
                        "pad:14, uint:17, bool, uint:10, uint:6, pad:2, uint:6, pad:2, uint:4"
                    )
                    prefix = "*"
                else:
                    sequence_number, is_kit, ean_pn, year, week, origin = snnew.unpack(
                        "pad:4, uint:17, bool, uint:10, uint:6, uint:6, uint:4"
                    )
                    prefix = ""

                sn = "%s%3sX%02u%02uX%03uX%c%05u" % (
                    prefix,
                    ot.get(origin, "UNK"),
                    week,
                    year,
                    ean_pn,
                    "K" if is_kit else "C",
                    sequence_number,
                )
                self.logger.info("SN: %s", sn)

        except Exception:
            self.logger.exception("CPU serial:")

        return sn, is_kit

    @staticmethod
    def _read_emmc_serial() -> str:
        with open(defines.emmc_serial_path) as f:
            return f.read().strip()

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
                    a = data["boot-status"]
                elif slot == "rootfs.1":
                    b = data["boot-status"]

            self.logger.info("Slot A boot status: %s", a)
            self.logger.info("Slot B boot status: %s", b)

            if a == "good" and b == "good":
                # Device is booting fine, remove stamp
                if os.path.isfile(defines.bootFailedStamp):
                    os.remove(defines.bootFailedStamp)

                return False

            self.logger.error("Detected broken boot slot !!!")
            # Device has boot problems
            if os.path.isfile(defines.bootFailedStamp):
                # The problem is already reported
                return False

            # This is a new problem, create stamp, report problem
            if not os.path.exists(defines.persistentStorage):
                os.makedirs(defines.persistentStorage)

            open(defines.bootFailedStamp, "a").close()
            return True

        except Exception:
            self.logger.exception("Failed to check for failed boot")
            # Something went wrong during check, expect the worst
            return True

    def eraseEeprom(self):
        self.mcc.do("!eecl")
        self.mcc.soft_reset()  # FIXME MC issue

    def getTiltProfilesNames(self):
        self.logger.debug(str(self._tiltProfileNames))
        return list(self._tiltProfileNames)

    def getTowerProfilesNames(self):
        self.logger.debug(str(self._towerProfileNames))
        return list(self._towerProfileNames)

    def getTiltProfiles(self):
        return self.getProfiles("?ticf")

    def getTowerProfiles(self):
        return self.getProfiles("?twcf")

    def getProfiles(self, getProfileDataCmd):
        profiles = []
        for profId in range(8):
            try:
                profData = self.mcc.do(getProfileDataCmd, profId).split(" ")
                profiles.append([int(x) for x in profData])
            except Exception:
                self.logger.exception("parse profile:")
                profiles.append(list((-1, -1, -1, -1, -1, -1, -1)))

        return profiles

    def setTiltProfiles(self, profiles):
        return self.setProfiles(profiles, "!tics", "!ticf")

    def setTowerProfiles(self, profiles):
        return self.setProfiles(profiles, "!twcs", "!twcf")

    def setProfiles(self, profiles, setProfileCmd, setProfileDataCmd):
        for profId in range(8):
            self.mcc.do(setProfileCmd, profId)
            self.mcc.do(setProfileDataCmd, *profiles[profId])

    def setTiltTempProfile(self, profileData):
        return self.setTempProfile(profileData, "!tics", "!ticf")

    def setTowerTempProfile(self, profileData):
        return self.setTempProfile(profileData, "!twcs", "!twcf")

    def setTempProfile(self, profileData, setProfileCmd, setProfileDataCmd):
        self.mcc.do(setProfileCmd, -1)
        self.mcc.do(setProfileDataCmd, *profileData)

    def getStallguardBuffer(self):
        samplesList = list()
        samplesCount = self.mcc.doGetInt("?sgbc")
        while samplesCount > 0:
            try:
                samples = self.mcc.doGetIntList("?sgbd", base=16)
                samplesCount -= len(samples)
                samplesList.extend(samples)
            except MotionControllerException:
                self.logger.exception("Problem reading stall guard buffer")
                break

        return samplesList

    def beep(self, frequency, lenght):
        if not self.config.mute:
            self.mcc.do("!beep", frequency, int(lenght * 1000))

    def beepEcho(self) -> None:
        try:
            self.beep(1800, 0.05)
        except MotionControllerException:
            self.logger.exception("Failed to beep")

    def beepRepeat(self, count):
        for _ in range(count):
            self.beep(1800, 0.1)
            sleep(0.5)

    def beepAlarm(self, count):
        for _ in range(count):
            self.beep(1900, 0.05)
            sleep(0.25)

    def powerLed(self, state):
        mode, speed = self._powerLedStates.get(state, (1, 1))
        self.powerLedMode = mode
        self.powerLedSpeed = speed

    @property
    def powerLedMode(self):
        return self.mcc.doGetInt("?pled")

    @powerLedMode.setter
    def powerLedMode(self, value):
        self.mcc.do("!pled", value)

    @property
    def powerLedPwm(self):
        try:
            pwm = self.mcc.do("?ppwm")
            return int(pwm) * 5
        except MotionControllerException:
            self.logger.exception("Failed to read power led pwm")
            return -1

    @powerLedPwm.setter
    def powerLedPwm(self, pwm):
        try:
            self.mcc.do("!ppwm", int(pwm / 5))
        except MotionControllerException:
            self.logger.exception("Failed to set power led pwm")

    @property
    @safe_call(-1, MotionControllerException)
    def powerLedSpeed(self):
        return self.mcc.doGetInt("?pspd")

    @powerLedSpeed.setter
    @safe_call(None, MotionControllerException)
    def powerLedSpeed(self, speed):
        self.mcc.do("!pspd", speed)

    def shutdown(self):
        self.mcc.do("!shdn", 5)

    def uvLed(self, state, time=0):
        self.mcc.do("!uled", 1 if state else 0, int(time))

    @safe_call([0, 0], (ValueError, MotionControllerException))
    def getUvLedState(self):
        uvData = self.mcc.doGetIntList("?uled")
        if uvData and len(uvData) < 3:
            return uvData if len(uvData) == 2 else list((uvData[0], 0))

        raise ValueError(f"UV data count not match! ({uvData})")

    @property
    def uvLedPwm(self):
        return self.mcc.doGetInt("?upwm")

    @uvLedPwm.setter
    def uvLedPwm(self, pwm):
        self.mcc.do("!upwm", int(pwm))

    @safe_call([0], (MotionControllerException, ValueError))
    def getUvStatistics(self):
        uvData = self.mcc.doGetIntList("?usta")  # time counter [s] #TODO add uv average current, uv average temperature
        if len(uvData) != 2:
            raise ValueError(f"UV statistics data count not match! ({uvData})")

        return uvData

    def saveUvStatistics(self):
        self.mcc.do("!usta", 0)

    def clearUvStatistics(self):  # call if UV led was replaced
        self.mcc.do("!usta", 1)

    def clearDisplayStatistics(self):  # call if print display was replaced
        self.mcc.do("!usta", 2)

    @safe_call([0, 0, 0, 0], (ValueError, MotionControllerException))
    def getVoltages(self):
        volts = self.mcc.doGetIntList("?volt", multiply=0.001)
        if len(volts) != 4:
            raise ValueError(f"Volts count not match! ({volts})")

        return volts

    def cameraLed(self, state):
        self.mcc.do("!cled", 1 if state else 0)

    def getCameraLedState(self):
        return self.mcc.doGetBool("?cled")

    def resinSensor(self, state):
        """Enable/Disable resin sensor"""
        self.mcc.do("!rsen", 1 if state else 0)

    def getResinSensor(self):
        """
        Read resin sensor enabled
        :return: True if enabled, False otherwise
        """
        return self.mcc.doGetBool("?rsen")

    def getResinSensorState(self):
        """
        Read resin sensor value
        :return: True if resin is detected, False otherwise
        """
        return self.mcc.doGetBool("?rsst")

    @safe_call(False, MotionControllerException)
    def isCoverClosed(self, check_for_updates: bool = True):
        return self.checkState("cover", check_for_updates)

    def isCoverVirtuallyClosed(self, check_for_updates: bool = True):
        """
        Check whenever the cover is closed or cover check is disabled
        """
        return self.isCoverClosed(check_for_updates=check_for_updates) or not self.config.coverCheck

    def getPowerswitchState(self):
        return self.checkState("button")

    @safe_call(False, MotionControllerException)
    def checkState(self, name, check_for_updates: bool = True):
        state = self.mcc.getStateBits([name], check_for_updates)
        return state[name]

    def startFans(self):
        self.setFans(mask={0: True, 1: True, 2: True})

    def stopFans(self):
        self.setFans(mask={0: False, 1: False, 2: False})

    def setFans(self, mask):
        out = list()
        for key in self.fans:
            if self.fans[key].enabled and mask.get(key):
                out.append(True)
            else:
                out.append(False)

        self.mcc.do("!frpm", " ".join(str(fan.targetRpm) for fan in self.fans.values()))
        self.mcc.doSetBoolList("!fans", out)

    def getFans(self, request=(0, 1, 2)):
        return self.getFansBits("?fans", request)

    @safe_call({0: False, 1: False, 2: False}, (MotionControllerException, ValueError))
    def getFansError(self):
        state = self.mcc.getStateBits(["fans"], check_for_updates=False)
        if "fans" not in state:
            raise ValueError(f"'fans' not in state: {state}")

        fansError = self.getFansBits("?fane", (0, 1, 2))
        return fansError

    def getFansBits(self, cmd, request):
        try:
            bits = self.mcc.doGetBoolList(cmd, bit_count=3)
            if len(bits) != 3:
                raise ValueError(f"Fans bits count not match! {bits}")

            return {idx: bits[idx] for idx in request}
        except (MotionControllerException, ValueError):
            self.logger.exception("getFansBits failed")
            return dict.fromkeys(request, False)

    def getFansRpm(self, request=(0, 1, 2)):
        try:
            rpms = self.mcc.doGetIntList("?frpm", multiply=1)
            if not rpms or len(rpms) != 3:
                raise ValueError(f"RPMs count not match! ({rpms})")

            return rpms
        except (MotionControllerException, ValueError):
            self.logger.exception("getFansRpm failed")
            return dict.fromkeys(request, 0)

    @safe_call([-273.2, -273.2, -273.2, -273.2], (MotionControllerException, ValueError))
    def getMcTemperatures(self, logTemps=True):
        temps = self.mcc.doGetIntList("?temp", multiply=0.1)
        if len(temps) != 4:
            raise ValueError(f"TEMPs count not match! ({temps})")

        if logTemps:
            self.logger.info("Temperatures [C]: %s", " ".join(["%.1f" % x for x in temps]))

        return temps

    def getUvLedTemperature(self):
        return self.getMcTemperatures(logTemps=False)[self._ledTempIdx]

    def getAmbientTemperature(self):
        return self.getMcTemperatures(logTemps=False)[self._ambientTempIdx]

    def getSensorName(self, sensorNumber):
        return _(self._sensorsNames.get(sensorNumber, N_("unknown sensor")))

    @safe_call(-273.2, Exception)
    def getCpuTemperature(self):  # pylint: disable=no-self-use
        with open(defines.cpuTempFile, "r") as f:
            return round((int(f.read()) / 1000.0), 1)

    # --- motors ---

    def motorsRelease(self):
        self.mcc.do("!motr")
        self._tiltSynced = False
        self._towerSynced = False

    def towerHoldTiltRelease(self):
        self.mcc.do("!ena 1")
        self._tiltSynced = False

    # --- tower ---

    def towerHomeCalibrateWait(self):
        self.mcc.do("!twhc")
        homingStatus = 1
        while homingStatus > 0:  # not done and not error
            homingStatus = self.towerHomingStatus
            sleep(0.1)

    @property
    def towerHomingStatus(self):
        return self.mcc.doGetInt("?twho")

    def towerSync(self):
        """ home is at top position """
        self._towerSynced = False
        self.mcc.do("!twho")

    def isTowerSynced(self):
        """ return tower status. False if tower is still homing or error occured """
        if not self._towerSynced:
            if self.towerHomingStatus == 0:
                self.setTowerPosition(self.config.towerHeight)
                self._towerSynced = True
            else:
                self._towerSynced = False

        return self._towerSynced

    @safe_call(False, MotionControllerException)
    def towerSyncWait(self, retries: int = 0):
        """ blocking method for tower homing. retries = number of additional tries when homing failes """
        if not self.isTowerMoving():
            self.towerSync()

        while True:
            homingStatus = self.towerHomingStatus
            if homingStatus == 0:
                self.setTowerPosition(self.config.towerHeight)
                self._towerSynced = True
                return True

            if homingStatus < 0:
                self.logger.warning("Tower homing failed! Status: %d", homingStatus)
                if retries < 1:
                    self.logger.error("Tower homing max tries reached!")
                    return False

                retries -= 1
                self.towerSync()

            sleep(0.25)

    def towerMoveAbsoluteWait(self, position):
        self.towerMoveAbsolute(position)
        while not self.isTowerOnPosition():
            sleep(0.1)

    @safe_call(None, MotionControllerException)
    def towerMoveAbsolute(self, position):
        self._towerToPosition = position
        self.mcc.do("!twma", position)

    def towerToPosition(self, mm):
        self.towerMoveAbsolute(self.config.calcMicroSteps(mm))

    # TODO use !brk instead. Motor might stall at !mot 0
    def towerStop(self):
        self.mcc.do("!mot", 0)

    def isTowerMoving(self):
        if self.mcc.doGetInt("?mot") & 1:
            return True

        return False

    @safe_call(False, MotionControllerException)
    def isTowerOnPosition(self, retries=None):
        """ check dest. position, retries = None is infinity """
        self._towerPositionRetries = retries
        if self.isTowerMoving():
            return False

        while self._towerToPosition != self.getTowerPositionMicroSteps():
            if self._towerPositionRetries is None or self._towerPositionRetries:
                if self._towerPositionRetries:
                    self._towerPositionRetries -= 1

                self.logger.warning(
                    "Tower is not on required position! Sync forced. Actual position: %d, Target position: %d ",
                    self.getTowerPositionMicroSteps(),
                    self._towerToPosition,
                )
                profileBackup = self._lastTowerProfile
                self.towerSyncWait()
                self.setTowerProfile(profileBackup)
                self.towerMoveAbsolute(self._towerToPosition)
                while self.isTowerMoving():
                    sleep(0.1)

            else:
                self.logger.error("Tower position max tries reached!")
                break

        return True

    def towerPositonFailed(self):
        return self._towerPositionRetries == 0

    def towerToZero(self):
        self.towerMoveAbsolute(self.config.calibTowerOffset)

    def isTowerOnZero(self):
        return self.isTowerOnPosition()

    def towerToTop(self):
        self.towerMoveAbsolute(self.config.towerHeight)

    def isTowerOnTop(self):
        return self.isTowerOnPosition()

    def setTowerOnMax(self):
        self.setTowerPosition(self._towerEnd)

    def towerToMax(self):
        self.towerMoveAbsolute(self._towerMax)

    def isTowerOnMax(self):
        stopped = not self.isTowerMoving()
        if stopped:
            self.setTowerOnMax()

        return stopped

    def towerToMin(self):
        self.towerMoveAbsolute(self._towerMin)

    def isTowerOnMin(self):
        stopped = not self.isTowerMoving()
        if stopped:
            self.setTowerPosition(0)

        return stopped

    @safe_call(None, MotionControllerException)
    def setTowerPosition(self, position):
        self.mcc.do("!twpo", position)

    @safe_call("ERROR", Exception)
    def getTowerPosition(self):
        steps = self.getTowerPositionMicroSteps()
        return "%.3f mm" % self.config.calcMM(int(steps))

    def getTowerPositionMicroSteps(self):
        steps = self.mcc.doGetInt("?twpo")
        return steps

    @safe_call(None, (ValueError, MotionControllerException))
    def setTowerProfile(self, profile):
        self._lastTowerProfile = profile
        profileId = self._towerProfiles.get(profile, None)
        if profileId is None:
            raise ValueError(f"Invalid tower profile '{profile}'")

        self.mcc.do("!twcs", profileId)

    @safe_call(None, (MotionControllerException, ValueError))
    def setTowerCurrent(self, current):  # pylint: disable=unused-argument,no-self-use
        return

    #        if 0 <= current <= 63:
    #            self.mcc.do("!twcu", current)
    #        else:
    #            self.logger.error("Invalid tower current %d", current)

    # metal vat:
    #  5.0 mm -  35 % -  68.5 ml
    # 10.0 mm -  70 % - 137.0 ml
    # 14.5 mm - 100 % - 200.0 ml
    # 35 % -  70 % : 1.0 mm = 13.7 ml
    # 70 % - 100 % : 1.0 mm = 14.0 ml

    # plastic vat:
    #  4.5 mm -  35 % -  66.0 ml (mostly same as metal vat)
    # 10.0 mm -  70 % - 146.5 ml
    # 13.6 mm - 100 % - 200.0 ml
    # 35 % -  70 % : 1.0 mm = 14.65 ml
    # 70 % - 100 % : 1.0 mm = 14.85 ml

    @safe_call(0, MotionControllerException)
    def get_precise_resin_volume_ml(self):
        self.setTowerProfile("homingFast")
        self.towerMoveAbsoluteWait(self._towerResinStartPos)  # move quickly to safe distance
        self.resinSensor(True)
        sleep(1)
        self.setTowerProfile("resinSensor")
        self.mcc.do("!rsme", self._towerResinStartPos - self._towerResinEndPos)  # relative movement!
        while self.isTowerMoving():
            sleep(0.1)

        position = self.getTowerPositionMicroSteps()
        self.resinSensor(False)
        if position == self._towerResinEndPos:
            return 0

        if self.config.vatRevision == 1:
            self.logger.debug("Using PLASTIC vat values")
            resin_constant = (14.65, 14.85)
        else:
            self.logger.debug("Using METALIC vat values")
            resin_constant = (13.7, 14.0)

        posMM = self.config.calcMM(position)
        if posMM < 10.0:
            volume = posMM * resin_constant[0]
        else:
            volume = posMM * resin_constant[1]

        return volume

    def getResinVolume(self):
        return int(round(self.get_precise_resin_volume_ml() / 10.0) * 10)

    @staticmethod
    def calcPercVolume(volume_ml):
        return 10 * ceil(10 * volume_ml / defines.resinMaxVolume)

    # --- tilt ---

    def tiltHomeCalibrateWait(self):
        self.mcc.do("!tihc")
        homingStatus = 1
        while homingStatus > 0:  # not done and not error
            homingStatus = self.tiltHomingStatus
            sleep(0.1)

    @property
    def tiltHomingStatus(self):
        return self.mcc.doGetInt("?tiho")

    def tiltSync(self):
        """home at bottom position"""
        self._tiltSynced = False
        self.mcc.do("!tiho")

    @safe_call(False, MotionControllerException)
    def isTiltSynced(self):
        """return tilt status. False if tilt is still homing or error occured"""
        if not self._tiltSynced:
            if self.tiltHomingStatus == 0:
                self.setTiltPosition(0)
                self._tiltSynced = True
            else:
                self._tiltSynced = False

        return self._tiltSynced

    @safe_call(False, MotionControllerException)
    def tiltSyncWait(self, retries: int = 0):
        """blocking method for tilt homing. retries = number of additional tries when homing fails"""
        if not self.isTiltMoving():
            self.tiltSync()

        while True:
            homingStatus = self.tiltHomingStatus
            if homingStatus == 0:
                self.setTiltPosition(0)
                self._tiltSynced = True
                return True

            if homingStatus < 0:
                self.logger.warning("Tilt homing failed! Status: %d", homingStatus)
                if retries < 1:
                    self.logger.error("Tilt homing max tries reached!")
                    return False

                retries -= 1
                self.tiltSync()

            sleep(0.25)

    def tiltMoveAbsolute(self, position):
        self._tiltToPosition = position
        self.mcc.do("!tima", position)

    def tiltStop(self):
        self.mcc.do("!mot", 0)

    def isTiltMoving(self):
        if self.mcc.doGetInt("?mot") & 2:
            return True

        return False

    def isTiltOnPosition(self):
        if self.isTiltMoving():
            return False

        if self.getTiltPositionMicroSteps() != self._tiltToPosition:
            self.logger.warning(
                "Tilt is not on required position! Sync forced. Actual position: %d, Target position: %d ",
                self.getTiltPositionMicroSteps(),
                self._tiltToPosition,
            )
            profileBackup = self._lastTiltProfile
            self.tiltSyncWait()
            self.setTiltProfile(profileBackup)
            self.tiltMoveAbsolute(self._tiltToPosition)
            while self.isTiltMoving():
                sleep(0.1)

            if self.getTiltPositionMicroSteps() != self._tiltToPosition:
                return False

        return True

    def tiltDown(self):
        self.tiltMoveAbsolute(0)

    def isTiltDown(self):
        return self.isTiltOnPosition()

    def tiltDownWait(self):
        self.tiltDown()
        while not self.isTiltDown():
            sleep(0.1)

    def tiltUp(self):
        self.tiltMoveAbsolute(self.config.tiltHeight)

    def isTiltUp(self):
        return self.isTiltOnPosition()

    def tiltUpWait(self):
        self.tiltUp()
        while not self.isTiltUp():
            sleep(0.1)

    def tiltToMax(self):
        self.tiltMoveAbsolute(self._tiltMax)

    def isTiltOnMax(self):
        stopped = not self.isTiltMoving()
        if stopped:
            self.setTiltPosition(self._tiltEnd)

        return stopped

    def tiltToMin(self):
        self.tiltMoveAbsolute(self._tiltMin)

    def isTiltOnMin(self):
        stopped = not self.isTiltMoving()
        if stopped:
            self.setTiltPosition(0)

        return stopped

    def tiltLayerDownWait(self, slowMove=False):
        tiltProfile = self.config.tuneTilt[0] if slowMove else self.config.tuneTilt[1]

        # initial release movement with optional sleep at the end
        self.setTiltProfile(self._tiltProfileNames[tiltProfile[0]])
        if tiltProfile[1] > 0:
            self.tiltMoveAbsolute(self.getTiltPositionMicroSteps() - tiltProfile[1])
            while self.isTiltMoving():
                sleep(0.1)

        sleep(tiltProfile[2] / 1000.0)

        # next movement may be splited
        self.setTiltProfile(self._tiltProfileNames[tiltProfile[3]])
        movePerCycle = int(self.getTiltPositionMicroSteps() / tiltProfile[4])
        for _ in range(tiltProfile[4]):
            self.tiltMoveAbsolute(self.getTiltPositionMicroSteps() - movePerCycle)
            while self.isTiltMoving():
                sleep(0.1)

            sleep(tiltProfile[5] / 1000.0)

        # if not already in endstop ensure we end up at defined bottom position
        if not self.checkState("endstop"):
            self.tiltMoveAbsolute(-defines.tiltHomingTolerance)
            while self.isTiltMoving():
                sleep(0.1)

        # check if tilt is on endstop
        if self.checkState("endstop"):
            if -defines.tiltHomingTolerance <= self.getTiltPositionMicroSteps() <= defines.tiltHomingTolerance:
                return True

        # unstuck
        self.logger.warning("Tilt unstucking")
        self.setTiltProfile("layerRelease")
        count = 0
        step = 128
        while count < self._tiltEnd and not self.checkState("endstop"):
            self.setTiltPosition(step)
            self.tiltMoveAbsolute(0)
            while self.isTiltMoving():
                sleep(0.1)

            count += step

        return self.tiltSyncWait(retries=1)

    def tiltLayerUpWait(self, slowMove=False):
        tiltProfile = self.config.tuneTilt[2] if slowMove else self.config.tuneTilt[3]

        self.setTiltProfile(self._tiltProfileNames[tiltProfile[0]])
        self.tiltMoveAbsolute(self.config.tiltHeight - tiltProfile[1])
        while self.isTiltMoving():
            sleep(0.1)

        sleep(tiltProfile[2] / 1000.0)
        self.setTiltProfile(self._tiltProfileNames[tiltProfile[3]])

        # finish move may be also splited in multiple sections
        movePerCycle = int((self.config.tiltHeight - self.getTiltPositionMicroSteps()) / tiltProfile[4])
        for _ in range(tiltProfile[4]):
            self.tiltMoveAbsolute(self.getTiltPositionMicroSteps() + movePerCycle)
            while self.isTiltMoving():
                sleep(0.1)

            sleep(tiltProfile[5] / 1000.0)

    def setTiltPosition(self, position):
        self.mcc.do("!tipo", position)

    # TODO: Get rid of this
    # TODO: Fix inconsistency getTowerPosition returns formated string with mm
    # TODO: Property could handle this a bit more consistently
    @safe_call("ERROR", MotionControllerException)
    def getTiltPosition(self):
        return self.getTiltPositionMicroSteps()

    def getTiltPositionMicroSteps(self):
        steps = self.mcc.doGetInt("?tipo")
        return steps

    def setTiltProfile(self, profile):
        self._lastTiltProfile = profile
        profileId = self._tiltProfiles.get(profile, None)
        if profileId is not None:
            self.mcc.do("!tics", profileId)
        else:
            self.logger.error("Invalid tilt profile '%s'", profile)

    @safe_call(None, (MotionControllerException, ValueError))
    def setTiltCurrent(self, current):
        if 0 <= current <= 63:
            self.mcc.do("!ticu", current)
        else:
            self.logger.error("Invalid tilt current %d", current)

    def tiltGotoFullstep(self, goUp: int = 0):
        self.mcc.do("!tigf", goUp)

    def stirResin(self):
        for _ in range(self.config.stirringMoves):
            self.setTiltProfile("homingFast")
            # do not verify end positions
            self.tiltUp()
            while self.isTiltMoving():
                sleep(0.1)

            self.tiltDown()
            while self.isTiltMoving():
                sleep(0.1)

            self.tiltSyncWait()

    def updateMotorSensitivity(self, tiltSensitivity=0, towerSensitivity=0):
        # adjust tilt profiles
        profiles = self.getTiltProfiles()
        profiles[0][4] = self.tiltAdjust["homingFast"][tiltSensitivity + 2][0]
        profiles[0][5] = self.tiltAdjust["homingFast"][tiltSensitivity + 2][1]
        profiles[1][4] = self.tiltAdjust["homingSlow"][tiltSensitivity + 2][0]
        profiles[1][5] = self.tiltAdjust["homingSlow"][tiltSensitivity + 2][1]
        self.setTiltProfiles(profiles)
        self.logger.info("tilt profiles changed to: %s", profiles)

        # adjust tower profiles
        profiles = self.getTowerProfiles()
        profiles[0][4] = self.towerAdjust["homingFast"][towerSensitivity + 2][0]
        profiles[0][5] = self.towerAdjust["homingFast"][towerSensitivity + 2][1]
        profiles[1][4] = self.towerAdjust["homingSlow"][towerSensitivity + 2][0]
        profiles[1][5] = self.towerAdjust["homingSlow"][towerSensitivity + 2][1]
        self.setTowerProfiles(profiles)
        self.logger.info("tower profiles changed to: %s", profiles)

    def tower_home(self) -> None:
        """
        Home tower axis
        """
        self.powerLed("warn")
        if not self.towerSyncWait():
            raise TowerHomeFailed()
        self.powerLed("normal")

    def tilt_home(self) -> None:
        """
        Home tilt axis
        """
        self.powerLed("warn")
        # assume tilt is up (there may be error from print)
        self.setTiltPosition(self.tilt_end)
        self.tiltLayerDownWait(True)
        if not self.tiltSyncWait():
            raise TiltHomeFailed()
        self.setTiltProfile("moveFast")
        self.tiltLayerUpWait()
        self.powerLed("normal")

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
            self.setTowerProfile("moveSlow" if abs(speed) < 2 else "homingFast")

        if speed > 0:
            if self._tower_moving:
                if self.isTowerOnMax():
                    return False
            else:
                self._tower_moving = True
                self.towerToMax()
            return True

        if speed < 0:
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

    def tilt_move(self, speed: int, set_profiles: bool = True, fullstep=False) -> bool:
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
            self.setTiltProfile("moveSlow" if abs(speed) < 2 else "homingFast")

        if speed != 0:
            self._tilt_move_last_position = self.tilt_position

        if speed > 0:
            if self._tilt_moving:
                if self.isTiltOnMax():
                    return False
            else:
                self._tilt_moving = True
                self.tiltToMax()
            return True

        if speed < 0:
            if self._tilt_moving:
                if self.isTiltOnMin():
                    return False
            else:
                self._tilt_moving = True
                self.tiltToMin()
            return True

        self.tiltStop()
        if fullstep:
            if self._tilt_move_last_position < self.tilt_position:
                self.tiltGotoFullstep(goUp=1)
            elif self._tilt_move_last_position > self.tilt_position:
                self.tiltGotoFullstep(goUp=0)
        self._tilt_move_last_position = None
        self._tilt_moving = False
        return True

    @property
    def tower_position_nm(self) -> int:
        """
        Read or set tower position in nm
        """
        # TODO: Raise exception if tower not synced
        microsteps = self.getTowerPositionMicroSteps()
        return self.config.tower_microsteps_to_nm(microsteps)

    @tower_position_nm.setter
    def tower_position_nm(self, position_nm: int) -> None:
        # TODO: This needs some safety check
        self.towerToPosition(position_nm / 1000 / 1000)

    @property
    def tilt_position(self) -> int:
        """
        Read or set tilt position in micro-steps
        """
        # TODO: Raise exception if tilt not synced
        return self.getTiltPositionMicroSteps()

    @tilt_position.setter
    def tilt_position(self, micro_steps: int):
        # TODO: This needs some safety check
        self.tiltMoveAbsolute(micro_steps)

    def get_tower_sensitivity(self) -> int:
        """
        Obtain tower sensitivity

        :return: Sensitivity value
        """

        tower_sensitivity = 0  # use default sensitivity first
        self.updateMotorSensitivity(self.config.tiltSensitivity, tower_sensitivity)
        tries = 3
        while tries > 0:
            self.towerSyncWait()
            home_status = self.towerHomingStatus
            if home_status == -2:
                raise TowerEndstopNotReached()
            if home_status == -3:
                # if homing failed try different tower homing profiles (only positive values of motor sensitivity)
                tower_sensitivity += 1  # try next motor sensitivity
                tries = 3  # start over with new sensitivity
                if tower_sensitivity >= len(self.towerAdjust["homingFast"]) - 2:
                    raise TowerHomeCheckFailed()

                self.updateMotorSensitivity(self.config.tiltSensitivity, tower_sensitivity)

                continue
            tries -= 1

        return tower_sensitivity

    def getFansRpmDict(self):
        rpms = self.getFansRpm()
        return {
            "uv_led": rpms[0],
            "blower": rpms[1],
            "rear": rpms[2]
        }

    def getTemperaturesDict(self):
        temps = self.getMcTemperatures(logTemps = False)
        return {
            'temp_led': temps[self._ledTempIdx],
            'temp_amb': temps[self._ambientTempIdx],
            'cpu_temp': self.getCpuTemperature()
        }
