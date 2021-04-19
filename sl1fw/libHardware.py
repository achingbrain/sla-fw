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

import asyncio
import functools
import logging
import os
import re
from math import ceil
from threading import Thread
from time import sleep

import json
import bitstring
import pydbus
from PySignal import Signal

from sl1fw import defines
from sl1fw.errors.errors import TowerHomeFailed, TowerEndstopNotReached, TowerHomeCheckFailed
from sl1fw.errors.exceptions import MotionControllerException
from sl1fw.configs.hw import HwConfig
from sl1fw.motion_controller.controller import MotionController
from sl1fw.utils.value_checker import ValueChecker
from sl1fw.hardware.exposure_screen import ExposureScreen
from sl1fw.hardware.printer_model import PrinterModel
from sl1fw.hardware.tilt import Tilt, TiltSL1
from sl1fw.functions.decorators import safe_call
from sl1fw.errors.exceptions import ConfigException
from sl1fw.hardware.sl1s_uvled_booster import Booster



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

        self._towerSynced = False

        self._lastTowerProfile = None

        self._towerToPosition = 0

        self._fanFailed = False
        self._coolDownCounter = 0
        self.led_temp_idx = 0
        self.ambient_temp_idx = 1

        # (mode, speed)
        self._powerLedStates = {"normal": (1, 2), "warn": (2, 10), "error": (3, 15), "off": (3, 64)}


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

        self._towerProfileNames = [x[0] for x in sorted(list(self._towerProfiles.items()), key=lambda kv: kv[1])]

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
            0: N_("UV LED temperature"),    # SL1
            1: N_("Ambient temperature"),
            2: N_("UV LED temperature"),    # SL1S
            3: N_("<reserved2>"),
        }

        self._towerMin = -self.config.calcMicroSteps(155)
        self._towerAboveSurface = -self.config.calcMicroSteps(145)
        self._towerMax = self.config.calcMicroSteps(310)
        self._towerEnd = self.config.calcMicroSteps(150)
        self._towerCalibPos = self.config.calcMicroSteps(1)
        self._towerResinStartPos = self.config.calcMicroSteps(36)
        self._towerResinEndPos = self.config.calcMicroSteps(1)

        self.mcc = MotionController(defines.motionControlDevice)

        self.tilt: Tilt = None

        self.boardData = self.readCpuSerial()
        self._emmc_serial = self._read_emmc_serial()

        self._tower_moving = False
        self._towerPositionRetries = None
        self._sl1s_booster = Booster()

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

    # MUST be called before start()
    def connect(self):
        self.printer_model = self.exposure_screen.start()
        self.mcc.connect(self.config.MCversionCheck)
        self.mc_sw_version_changed.emit()
        if self.printer_model == PrinterModel.SL1S:
            self._sl1s_booster.connect()
            self.led_temp_idx = 2

    def start(self):
        if self.printer_model == PrinterModel.SL1 or self.printer_model == PrinterModel.SL1S:
            self.tilt = TiltSL1(self.mcc,self.config)
        self.initDefaults()
        self._value_refresh_thread.start()

    def exit(self):
        self._value_refresh_run = False
        self._value_refresh_thread.join()
        self.mcc.exit()
        self.exposure_screen.exit()

    def _value_refresh_body(self):
        checkers = [
            ValueChecker(self.getFansRpm, self.fans_changed, False),
            ValueChecker(functools.partial(self.getMcTemperatures, False), self.mc_temps_changed),
            ValueChecker(self.getCpuTemperature, self.cpu_temp_changed),
            ValueChecker(self.getVoltages, self.led_voltages_changed),
            ValueChecker(self.getResinSensorState, self.resin_sensor_state_changed),
            ValueChecker(self.getUvStatistics, self.uv_statistics_changed),
            ValueChecker(self.mcc.getStateBits, None),
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
        if self.config.lockProfiles:
            self.logger.warning("Printer profiles will not be overwriten")
        else:
            if self.printer_model == PrinterModel.SL1 or self.printer_model == PrinterModel.SL1S:
                with open(os.path.join(defines.dataPath, self.printer_model.name, "default." + defines.tiltProfilesSuffix), "r") as f:
                    defaultProfiles = json.loads(f.read())
                    mcProfiles = self.tilt.profiles
                    if mcProfiles != defaultProfiles:
                        self.logger.info("Overwriting tilt profiles to: %s", defaultProfiles)
                        self.tilt.profiles = defaultProfiles
                        self.tilt.sensitivity(self.config.tiltSensitivity)
                with open(os.path.join(defines.dataPath, self.printer_model.name, "default." + defines.tuneTiltProfilesSuffix), "r") as f:
                    tuneTilt = json.loads(f.read())
                    writer = self.config.get_writer()
                    if tuneTilt != writer.tuneTilt:
                        self.logger.info("Overwriting tune tilt profiles to: %s", tuneTilt)
                        writer.tuneTilt = tuneTilt
                        try:
                            writer.commit()
                        except Exception as e:
                            raise ConfigException() from e


    def flashMC(self):
        self.mcc.flash(self.config.MCBoardVersion)

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

    def getTowerProfilesNames(self):
        return list(self._towerProfileNames)

    def getTowerProfiles(self):
        return self.getProfiles("?twcf")

    def setProfiles(self, profiles, setProfileCmd, setProfileDataCmd):
        for profId in range(8):
            self.mcc.do(setProfileCmd, profId)
            self.mcc.do(setProfileDataCmd, *profiles[profId])

    def setTowerProfiles(self, profiles):
        return self.setProfiles(profiles, "!twcs", "!twcf")

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
    def uvLedPwm(self) -> int:
        if self.printer_model == PrinterModel.SL1S:
            return self._sl1s_booster.pwm
        return self.mcc.doGetInt("?upwm")

    @uvLedPwm.setter
    def uvLedPwm(self, pwm) -> None:
        if self.printer_model == PrinterModel.SL1S:
            self._sl1s_booster.pwm = int(pwm)
        else:
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
        return [round(volt, 1) for volt in volts]

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
        return self.mcc.checkState("cover", check_for_updates)

    def isCoverVirtuallyClosed(self, check_for_updates: bool = True):
        """
        Check whenever the cover is closed or cover check is disabled
        """
        return self.isCoverClosed(check_for_updates=check_for_updates) or not self.config.coverCheck

    def getPowerswitchState(self):
        return self.mcc.checkState("button")

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
        self.mcc.doSetBoolList("!fans", out)
        self.mcc.do("!frpm", " ".join(str(fan.targetRpm) for fan in self.fans.values()))

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


    def uvFanRpmControl(self):
        if self.config.rpmControlOverride:
            return
        uvLedTemperature = self.getUvLedTemperature()
        mapConstant = (self.config.rpmControlUvFanMaxRpm - self.config.rpmControlUvFanMinRpm) / (self.config.rpmControlUvLedMaxTemp - self.config.rpmControlUvLedMinTemp)
        uvFanTempRpm = round((uvLedTemperature - self.config.rpmControlUvLedMinTemp) * mapConstant + self.config.rpmControlUvFanMinRpm)
        if uvFanTempRpm > defines.fanMaxRPM[0]:
            uvFanTempRpm = defines.fanMaxRPM[0]
        elif uvFanTempRpm < defines.fanMinRPM:
            uvFanTempRpm = defines.fanMinRPM
        fansRpm = [uvFanTempRpm, self.fans[1].targetRpm, self.fans[2].targetRpm]
        self.mcc.do("!frpm", " ".join(str(fan) for fan in fansRpm))

    @safe_call([-273.2, -273.2, -273.2, -273.2], (MotionControllerException, ValueError))
    def getMcTemperatures(self, logTemps=True):
        temps = self.mcc.doGetIntList("?temp", multiply=0.1)
        if len(temps) != 4:
            raise ValueError(f"TEMPs count not match! ({temps})")

        if logTemps:
            self.logger.info("Temperatures [C]: %s", " ".join(["%.1f" % x for x in temps]))

        return [round(temp, 1) for temp in temps]

    def getUvLedTemperature(self):
        return self.getMcTemperatures(logTemps=False)[self.led_temp_idx]

    def getAmbientTemperature(self):
        return self.getMcTemperatures(logTemps=False)[self.ambient_temp_idx]

    def getSensorName(self, sensorNumber):
        return _(self._sensorsNames.get(sensorNumber, N_("unknown sensor")))

    @safe_call(-273.2, Exception)
    def getCpuTemperature(self):  # pylint: disable=no-self-use
        with open(defines.cpuTempFile, "r") as f:
            return round((int(f.read()) / 1000.0), 1)

    # --- motors ---

    def motorsRelease(self):
        self.mcc.do("!motr")
        self._towerSynced = False

    def towerHoldTiltRelease(self):
        self.mcc.do("!ena 1")

    @safe_call(False, MotionControllerException)
    def motorsStop(self):
        self.mcc.do("!mot", 0)

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
        return asyncio.run(self.towerSyncWaitAsync(retries=retries))

    @safe_call(False, MotionControllerException)
    async def towerSyncWaitAsync(self, retries: int = 0):
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

            await asyncio.sleep(0.25)

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
        self.mcc.do("!mot", 2)

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

    # TODO: Get rid of this
    # TODO: Fix inconsistency getTowerPosition returns formated string with mm
    # TODO: Property could handle this a bit more consistently
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

    def updateMotorSensitivity(self, tiltSensitivity=0, towerSensitivity=0):
        self.tilt.sensitivity(tiltSensitivity)

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

    def get_tower_sensitivity(self) -> int:
        """
        Obtain tower sensitivity

        :return: Sensitivity value
        """
        return asyncio.run(self.get_tower_sensitivity_async())

    async def get_tower_sensitivity_async(self) -> int:
        """
        Obtain tower sensitivity

        :return: Sensitivity value
        """

        tower_sensitivity = 0  # use default sensitivity first
        self.updateMotorSensitivity(self.config.tiltSensitivity, tower_sensitivity)
        tries = 3
        while tries > 0:
            await self.towerSyncWaitAsync()
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
            'temp_led': temps[self.led_temp_idx],
            'temp_amb': temps[self.ambient_temp_idx],
            'cpu_temp': self.getCpuTemperature()
        }
