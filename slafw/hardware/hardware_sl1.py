# This file is part of the SLA firmware
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
import json
import os
from asyncio import Task, CancelledError
from datetime import timedelta
from functools import cached_property, partial
from math import ceil
from threading import Thread
from time import sleep, monotonic
from typing import List, Optional, Any, Tuple

from slafw import defines
from slafw.configs.hw import HwConfig
from slafw.errors.errors import TowerHomeFailed, TowerEndstopNotReached, \
    MotionControllerException, ConfigException
from slafw.functions.decorators import safe_call
from slafw.hardware.axis import AxisId
from slafw.hardware.fan import Fan
from slafw.hardware.printer_model import PrinterModel
from slafw.hardware.sl1.exposure_screen import ExposureScreenSL1
from slafw.hardware.sl1.tilt import TiltSL1
from slafw.hardware.sl1.uv_led import UvLedSL1
from slafw.hardware.sl1s_uvled_booster import Booster
from slafw.hardware.tilt import TiltProfile
from slafw.hardware.base.hardware import BaseHardware
from slafw.motion_controller.controller import MotionController
from slafw.utils.value_checker import ValueChecker, UpdateInterval
from slafw.hardware.power_led_action import WarningAction
from slafw.hardware.sl1.power_led import PowerLedSL1


class HardwareSL1(BaseHardware):
    FAN_CONTROL_MIN_DELAY_S = 30

    def __init__(self, hw_config: HwConfig, printer_model: PrinterModel):
        super().__init__(hw_config, printer_model)

        self.mcc = MotionController(defines.motionControlDevice)
        self.sl1s_booster = Booster()
        self.exposure_screen = ExposureScreenSL1(printer_model)

        self._printer_model = printer_model
        self.towerSynced = False

        self._lastTowerProfile = None

        self._towerToPosition = 0

        self._fanFailed = False
        self._coolDownCounter = 0
        self.led_temp_idx = 0
        self.ambient_temp_idx = 1

        self._towerProfiles = {
            "homingFast": 0,
            "homingSlow": 1,
            "moveFast": 2,
            "moveSlow": 3,
            "layer": 4,
            "layerMove": 5,
            "superSlow": 6,
            "resinSensor": 7,
        }

        self._towerProfileNames = [x[0] for x in sorted(list(self._towerProfiles.items()), key=lambda kv: kv[1])]

        self.towerAdjust = {
            #               -2      -1      0     +1     +2
            "homingFast": [[22, 0], [22, 2], [22, 4], [22, 6], [22, 8]],
            "homingSlow": [[14, 0], [15, 0], [16, 1], [16, 3], [16, 5]],
        }



        self.config.add_onchange_handler(self._fan_values_refresh)

        self._sensorsNames = {
            0: N_("UV LED temperature"),    # SL1
            1: N_("Ambient temperature"),
            2: N_("UV LED temperature"),    # SL1S
            3: N_("<reserved2>"),
        }

        self._tower_moving = False
        self._towerPositionRetries: int = 1

        self._value_refresh_thread = Thread(daemon=True, target=self._value_refresh_body)
        self._value_refresh_task: Optional[Task] = None

        self.check_cover_override = False

        self.mcc.power_button_changed.connect(self.power_button_state_changed.emit)
        self.mcc.cover_state_changed.connect(self.cover_state_changed.emit)
        self.mcc.fans_state_changed.connect(lambda x: self.fans_changed.emit())
        self.mcc.tower_status_changed.connect(lambda x: self.tower_position_changed.emit())
        self.mcc.tilt_status_changed.connect(lambda x: self.tilt_position_changed.emit())
        self.cpu_temp_changed.connect(self._check_cpu_overheat)
        self.mc_temps_changed.connect(self._check_uv_led_overheat)
        self.mc_temps_changed.connect(self.uv_fan_rpm_control)
        self.mcc.fans_state_changed.connect(self._fans_error_check)

        self._tilt_position_checker = ValueChecker(
            lambda: self.tilt.position,
            self.tilt_position_changed,
            UpdateInterval.seconds(5),
            pass_value=False,
        )
        self._tower_position_checker = ValueChecker(
            lambda: self.tower_position_nm,
            self.tower_position_changed,
            UpdateInterval.seconds(5),
            pass_value=False,
        )
        self.mcc.tilt_status_changed.connect(self._tilt_position_checker.set_rapid_update)
        self.mcc.tower_status_changed.connect(self._tower_position_checker.set_rapid_update)
        self.last_rpm_control: Optional[float] = None

        self.uv_fan = Fan(
            N_("UV LED fan"), defines.fanMaxRPM[0], self.config.fan1Rpm, self.config.fan1Enabled, auto_control=True
        )
        self.blower_fan = Fan(N_("blower fan"), defines.fanMaxRPM[1], self.config.fan2Rpm, self.config.fan2Enabled)
        self.rear_fan = Fan(N_("rear fan"), defines.fanMaxRPM[2], self.config.fan3Rpm, self.config.fan3Enabled)
        self.fans = {
            0: self.uv_fan,
            1: self.blower_fan,
            2: self.rear_fan,
        }

    @cached_property
    def tower_min_nm(self) -> int:
        return -(self.config.max_tower_height_mm + 5) * 1_000_000

    @cached_property
    def tower_above_surface_nm(self) -> int:
        return -(self.config.max_tower_height_mm - 5) * 1_000_000

    @cached_property
    def tower_max_nm(self) -> int:
        return 2 * self.config.max_tower_height_mm * 1_000_000

    @cached_property
    def tower_end_nm(self) -> int:
        return self.config.max_tower_height_mm * 1_000_000

    @cached_property
    def tower_calib_pos_nm(self) -> int:  # pylint: disable=no-self-use
        return 1_000_000

    @cached_property
    def _tower_resin_start_pos_nm(self) -> int:  # pylint: disable=no-self-use
        return 36_000_000

    @cached_property
    def _tower_resin_end_pos_nm(self) -> int:  # pylint: disable=no-self-use
        return 1_000_000

    # MUST be called before start()
    def connect(self):
        # MC have to be started first (beep, poweroff)
        self.mcc.connect(self.config.MCversionCheck)
        self.mc_sw_version_changed.emit()
        self.exposure_screen.start()

        self.uv_led = UvLedSL1(self.mcc, self._printer_model)
        self.tilt = TiltSL1(self.mcc, self.config)
        self.power_led = PowerLedSL1(self.mcc)

        if self._printer_model.options.has_booster:
            self.sl1s_booster.connect()
            self.led_temp_idx = 2

    def start(self):
        self.initDefaults()
        self._value_refresh_thread.start()

    def exit(self):
        if self._value_refresh_thread.is_alive():
            while not self._value_refresh_task:
                sleep(0.1)
            self._value_refresh_task.cancel()
            self._value_refresh_thread.join()
        self.mcc.exit()
        self.exposure_screen.exit()

    async def _value_refresh_task_body(self):
        checkers = [
            ValueChecker(self.getFansRpm, self.fans_changed, UpdateInterval.seconds(3), pass_value=False),
            ValueChecker(
                partial(self.getMcTemperatures, False), self.mc_temps_changed, UpdateInterval.seconds(3),
            ),
            ValueChecker(self.getCpuTemperature, self.cpu_temp_changed, UpdateInterval.seconds(3)),
            ValueChecker(self.getVoltages, self.led_voltages_changed, UpdateInterval.seconds(5)),
            ValueChecker(self.getResinSensorState, self.resin_sensor_state_changed),
            ValueChecker(self.getUvStatistics, self.uv_statistics_changed, UpdateInterval.seconds(30)),
            self._tilt_position_checker,
            self._tower_position_checker,
            ValueChecker(self.mcc.getStateBits, None, UpdateInterval(timedelta(milliseconds=500))),
        ]

        self._value_refresh_task = asyncio.gather(*[checker.check() for checker in checkers])
        await self._value_refresh_task

    def _value_refresh_body(self):
        try:
            asyncio.run(self._value_refresh_task_body())
        except CancelledError:
            pass # This is normal printer shutdown
        except Exception:
            self.logger.exception("Value checker thread crashed")
            # Overheat check is not working, assuming we are overheated
            self.uv_led_overheat = True
            self.uv_led_overheat_changed.emit(True)
            raise
        finally:
            self.logger.info("Value refresh checker thread ended")

    def _fan_values_refresh(self, key: str, _: Any):
        """ Re-load the fan RPM settings from configuration, should be used as a callback """
        if key in {"fan1Rpm", "fan2Rpm", "fan3Rpm", "fan1Enabled", "fan2Enabled", "fan3Enabled", }:
            self.fans[0].default_rpm = self.config.fan1Rpm
            self.fans[0].enabled = self.config.fan1Enabled
            self.fans[1].default_rpm = self.config.fan2Rpm
            self.fans[1].enabled = self.config.fan2Enabled
            self.fans[2].default_rpm = self.config.fan3Rpm
            self.fans[2].enabled = self.config.fan3Enabled
            mask = self.getFans()
            self.setFans(mask)

    def initDefaults(self):
        self.motorsRelease()
        self.uvLedPwm = self.config.uvPwm
        self.power_led.intensity = self.config.pwrLedPwm
        self.resinSensor(False)
        self.stopFans()
        if self.config.lockProfiles:
            self.logger.warning("Printer profiles will not be overwriten")
        else:
            if self._printer_model.options.has_tilt:
                for axis in AxisId:
                    if axis is AxisId.TOWER:
                        suffix = defines.towerProfilesSuffix
                        sensitivity = self.config.towerSensitivity
                        mc_profiles = self.getTowerProfiles()
                    else:
                        suffix = defines.tiltProfilesSuffix
                        sensitivity = self.config.tiltSensitivity
                        mc_profiles = self.tilt.profiles
                    with open(os.path.join(defines.dataPath, self._printer_model.name, "default." + suffix), "r") as f:
                        profiles = json.loads(f.read())
                        profiles = self.get_profiles_with_sensitivity(profiles, axis, sensitivity)
                        if mc_profiles != profiles:
                            self.logger.info("Overwriting %s profiles to: %s", axis.name, profiles)
                            if axis is AxisId.TOWER:
                                self.setTowerProfiles(profiles)
                            else:
                                self.tilt.profiles = profiles
                with open(os.path.join(defines.dataPath, self._printer_model.name, "default." + defines.tuneTiltProfilesSuffix), "r") as f:
                    tuneTilt = json.loads(f.read())
                    writer = self.config.get_writer()
                    if tuneTilt != writer.tuneTilt:
                        self.logger.info("Overwriting tune tilt profiles to: %s", tuneTilt)
                        writer.tuneTilt = tuneTilt
                        try:
                            writer.commit()
                        except Exception as e:
                            raise ConfigException() from e

            self.tilt.movement_ended.connect(lambda: self._tilt_position_checker.set_rapid_update(False))

    def flashMC(self):
        self.mcc.flash(self.config.MCBoardVersion)

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

    def beep(self, frequency_hz: int, length_s: float):
        try:
            if not self.config.mute:
                self.mcc.do("!beep", frequency_hz, int(length_s * 1000))
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

    def uvLed(self, state, time_ms=0):
        if state and self.uv_led_overheat:
            self.logger.error("Blocking attempt to set overheated UV LED on")
            return

        self.mcc.do("!uled", 1 if state else 0, int(time_ms))

    @safe_call([0, 0], (ValueError, MotionControllerException))
    def getUvLedState(self):
        uvData = self.mcc.doGetIntList("?uled")
        if uvData and len(uvData) < 3:
            return uvData if len(uvData) == 2 else list((uvData[0], 0))

        raise ValueError(f"UV data count not match! ({uvData})")

    @property
    def uvLedPwm(self) -> int:
        if self._printer_model.options.has_booster:
            return self.sl1s_booster.pwm
        return self.mcc.doGetInt("?upwm")

    @uvLedPwm.setter
    def uvLedPwm(self, pwm) -> None:
        if self._printer_model.options.has_booster:
            self.sl1s_booster.pwm = int(pwm)
        else:
            self.mcc.do("!upwm", int(pwm))

    @safe_call([0], (MotionControllerException, ValueError))
    def getUvStatistics(self) -> Tuple[Any, Any]:
        uvData = self.mcc.doGetIntList("?usta")  # time counter [s] #TODO add uv average current, uv average temperature
        if len(uvData) != 2:
            raise ValueError(f"UV statistics data count not match! ({uvData})")

        return uvData

    def saveUvStatistics(self):
        self.mcc.do("!usta", 0)

    def clearUvStatistics(self):
        """
        Call if UV led was replaced
        """
        self.mcc.do("!usta", 1)

    def clearDisplayStatistics(self):
        """
        Call if print display was replaced
        """
        self.mcc.do("!usta", 2)
        try:
            os.remove(defines.displayUsageData)
        except Exception:
            self.logger.exception("Display usage data file was not deleted.")

    @safe_call(None, MotionControllerException)
    def uvDisplayCounter(self, mask) -> None:
        self.mcc.do("!ulcd", int(mask))

    @safe_call([0, 0, 0, 0], (ValueError, MotionControllerException))
    def getVoltages(self, precision = 3):
        volts = self.mcc.doGetIntList("?volt", multiply=0.001)
        if len(volts) != 4:
            raise ValueError(f"Volts count not match! ({volts})")
        return [round(volt, precision) for volt in volts]

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
        self.mcc.do("!frpm", " ".join(str(fan.target_rpm) for fan in self.fans.values()))

    def getFans(self, request=(0, 1, 2)):
        return self.getFansBits("?fans", request)

    @safe_call({0: False, 1: False, 2: False}, (MotionControllerException, ValueError))
    def getFansError(self):
        state = self.mcc.getStateBits(["fans"], check_for_updates=False)
        if "fans" not in state:
            raise ValueError(f"'fans' not in state: {state}")

        fansError = self.getFansBits("?fane", (0, 1, 2))
        return fansError

    def getFansErrorText(self) -> str:
        failed_fans = []
        fans_state = self.getFansError()
        for num, state in fans_state.items():
            if state:
                failed_fans.append(self.fans[num].name)
        return ", ".join(failed_fans)

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

    def setFansRpm(self, rpms: List[int]):
        self.mcc.do("!frpm", " ".join(str(fan) for fan in rpms))

    def uv_fan_rpm_control(self, temps: List[float]):
        if self.last_rpm_control and monotonic() - self.last_rpm_control < self.FAN_CONTROL_MIN_DELAY_S:
            # Avoid too frequent controls, MC does not report errors a few seconds after control
            return

        if self.config.rpmControlOverride or not self.fans[0].auto_control:
            self.logger.debug("Skipping auto UV fan control - disabled")
            return

        uv_led_temperature = temps[self.led_temp_idx]
        max_rpm = self.config.rpmControlUvFanMaxRpm
        min_rpm = self.config.rpmControlUvFanMinRpm
        max_temp = self.config.rpmControlUvLedMaxTemp
        min_temp = self.config.rpmControlUvLedMinTemp
        map_constant = (max_rpm - min_rpm) / (max_temp - min_temp)
        uv_fan_temp_rpm = round((uv_led_temperature - min_temp) * map_constant + min_rpm)
        uv_fan_temp_rpm = max(min(uv_fan_temp_rpm, defines.fanMaxRPM[0]), defines.fanMinRPM)
        fans_rpm = [uv_fan_temp_rpm, self.fans[1].target_rpm, self.fans[2].target_rpm]
        self.logger.debug("Fan RPM control setting RPMs: %s", fans_rpm)
        self.last_rpm_control = monotonic()
        self.setFansRpm(fans_rpm)

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

    def _check_uv_led_overheat(self, temperatures: List[int]) -> None:
        # TODO: Refactor temp (all value read) using some cache to avoid parsing at multiple places
        temp = temperatures[self.led_temp_idx]
        # TODO: < 0 is not an overheat, it is rather a read error (or it is an actual temperature)
        old = self.uv_led_overheat
        if temp < 0 or temp > defines.maxUVTemp:
            self.logger.error("UV LED is overheating, temperature: %f", temp)
            self.uv_led_overheat = True
        if 0 < temp < defines.maxUVTemp - defines.uv_temp_hysteresis:
            self.uv_led_overheat = False
        if old != self.uv_led_overheat:
            self.uv_led_overheat_changed.emit(self.uv_led_overheat)

    def _fans_error_check(self, fans_error: bool):
        """
        Report fan failure

        @param fans_error: fan operation status, True - working, False - broken
        """
        error = self.getFansError()
        if not any(error.values()):
            self.logger.debug("Ignoring fan error from status as no fan is failing")
            fans_error = False  # False positive, fans are actually ok ???

        if self.fans_error != fans_error:
            self.fans_error = fans_error
            self.fans_error_changed.emit(error)

    def getAmbientTemperature(self):
        return self.getMcTemperatures(logTemps=False)[self.ambient_temp_idx]

    def getSensorName(self, sensorNumber):
        return _(self._sensorsNames.get(sensorNumber, N_("unknown sensor")))

    def _check_cpu_overheat(self, A64temperature):
        if A64temperature > defines.maxA64Temp: # 80 C
            self.logger.warning("Printer is overheating! Measured %.1f °C on A64.", A64temperature)
            if not any(fan.enabled for fan in self.fans.values()):
                self.startFans()
            #self.checkCooling = True #shouldn't this start the fan check also?

    # --- motors ---

    def motorsRelease(self):
        self.mcc.do("!motr")
        self.towerSynced = False

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
        self.towerSynced = False
        self.mcc.do("!twho")

    def isTowerSynced(self):
        """ return tower status. False if tower is still homing or error occured """
        if not self.towerSynced:
            if self.towerHomingStatus == 0:
                self.set_tower_position_nm(self.config.tower_height_nm)
                self.towerSynced = True
            else:
                self.towerSynced = False

        return self.towerSynced

    @safe_call(False, MotionControllerException)
    def towerSyncWait(self, retries: int = 2):
        """ blocking method for tower homing. retries = number of additional tries when homing failes """
        return asyncio.run(self.towerSyncWaitAsync(retries=retries))

    @safe_call(False, MotionControllerException)
    async def towerSyncWaitAsync(self, retries: int = 2):
        """ blocking method for tower homing. retries = number of additional tries when homing failes """
        if not self.isTowerMoving():
            self.towerSync()

        while True:
            homingStatus = self.towerHomingStatus
            if homingStatus == 0:
                self.set_tower_position_nm(self.config.tower_height_nm)
                self.towerSynced = True
                return True

            if homingStatus < 0:
                self.logger.warning("Tower homing failed! Status: %d", homingStatus)
                if retries < 1:
                    self.logger.error("Tower homing max tries reached!")
                    if homingStatus == -2:
                        raise TowerEndstopNotReached()
                    if homingStatus == -3:
                        raise TowerHomeFailed()

                retries -= 1
                self.towerSync()

            await asyncio.sleep(0.25)

    def _towerMoveAbsolute(self, position: int):
        self._towerToPosition = position
        self.mcc.do("!twma", position)

    # TODO use !brk instead. Motor might stall at !mot 0
    def towerStop(self):
        self.mcc.do("!mot", 2)

    def isTowerMoving(self):
        if self.mcc.doGetInt("?mot") & 1:
            return True
        return False

    @safe_call(False, MotionControllerException)
    async def isTowerOnPositionAsync(self, retries: int = 1) -> bool:
        """ check dest. position, retries = None is infinity """
        self._towerPositionRetries = retries
        if self.isTowerMoving():
            return False

        while self._towerToPosition != self._getTowerPositionMicroSteps():
            if self._towerPositionRetries:
                self._towerPositionRetries -= 1

                self.logger.warning(
                    "Tower is not on required position! Sync forced. Actual position: %d, Target position: %d ",
                    self._getTowerPositionMicroSteps(),
                    self._towerToPosition,
                )
                profileBackup = self._lastTowerProfile
                await self.towerSyncWaitAsync()
                self.setTowerProfile(profileBackup)
                self._towerMoveAbsolute(self._towerToPosition)
                while self.isTowerMoving():
                    await asyncio.sleep(0.1)

            else:
                self.logger.error("Tower position max tries reached!")
                break

        return True

    def towerPositonFailed(self):
        return self._towerPositionRetries == 0

    def towerToZero(self):
        self.tower_position_nm = self.config.calib_tower_offset_nm

    def towerToTop(self):
        self.tower_position_nm = self.config.tower_height_nm

    def setTowerOnMax(self):
        self.set_tower_position_nm(self.tower_end_nm)

    def towerToMax(self):
        self.tower_position_nm = self.tower_max_nm

    def isTowerOnMax(self):
        stopped = not self.isTowerMoving()
        if stopped:
            self.setTowerOnMax()

        return stopped

    def towerToMin(self):
        self.tower_position_nm = self.tower_min_nm

    def isTowerOnMin(self):
        stopped = not self.isTowerMoving()
        if stopped:
            self.set_tower_position_nm(0)

        return stopped

    def _getTowerPositionMicroSteps(self):
        steps = self.mcc.doGetInt("?twpo")
        return steps

    def set_tower_position_nm(self, position_nm: int):
        self.mcc.do("!twpo", self.config.nm_to_tower_microsteps(position_nm))

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

    def get_precise_resin_volume_ml(self) -> float:
        return asyncio.run(self.get_precise_resin_volume_ml_async())

    async def get_precise_resin_volume_ml_async(self) -> float:
        if self.config.vatRevision == 1:
            self.logger.debug("Using PLASTIC vat values")
            resin_constant = (14.65, 14.85)
        else:
            self.logger.debug("Using METALIC vat values")
            resin_constant = (13.7, 14.0)
        pos_mm = await self.get_resin_sensor_position_mm()
        if pos_mm < 10.0:
            volume = pos_mm * resin_constant[0]
        else:
            volume = pos_mm * resin_constant[1]
        return volume

    async def get_resin_volume_async(self) -> int:
        return int(round(await self.get_precise_resin_volume_ml_async() / 10.0) * 10)

    @staticmethod
    def calcPercVolume(volume_ml):
        return 10 * ceil(10 * volume_ml / defines.resinMaxVolume)

    async def tower_to_resin_measurement_start_position(self):
        self.setTowerProfile("homingFast")
        await self.tower_move_absolute_nm_wait_async(self._tower_resin_start_pos_nm)  # move quickly to safe distance

    @safe_call(0, MotionControllerException)
    async def get_resin_sensor_position_mm(self) -> float:
        await self.tower_to_resin_measurement_start_position()
        try:
            self.resinSensor(True)
            await asyncio.sleep(1)
            self.setTowerProfile("resinSensor")
            relative_move_nm = self._tower_resin_start_pos_nm - self._tower_resin_end_pos_nm
            self.mcc.do("!rsme", self.config.nm_to_tower_microsteps(relative_move_nm))
            while self.isTowerMoving():
                await asyncio.sleep(0.1)
            if not self.getResinSensorState():
                self.logger.error("Resin sensor was not triggered")
                return 0.0
        finally:
            self.resinSensor(False)
        return self.tower_position_nm / 1_000_000

    def get_profiles_with_sensitivity(self, profiles: List[List[int]], axis: AxisId, sens: int = 0):
        if sens < -2 or sens > 2:
            raise ValueError("`axis` sensitivity must be from -2 to +2", axis)

        sens_dict = self.towerAdjust
        if axis is AxisId.TILT:
            sens_dict = self.tilt.sensitivity_dict
        profiles[0][4:6] = sens_dict["homingFast"][sens + 2]
        profiles[1][4:6] = sens_dict["homingSlow"][sens + 2]
        return profiles

    def updateMotorSensitivity(self, axis: AxisId, sens: int = 0):
        if axis is AxisId.TOWER:
            profiles = self.getTowerProfiles()
        else:
            profiles = self.tilt.profiles
        self.get_profiles_with_sensitivity(profiles, axis, sens)
        if axis is AxisId.TOWER:
            self.setTowerProfiles(profiles)
        else:
            self.tilt.profiles = profiles
        self.logger.info("%s profiles changed to: %s", axis.name, profiles)

    def tower_home(self) -> None:
        """
        Home tower axis
        """
        with WarningAction(self.power_led):
            if not self.towerSyncWait():
                raise TowerHomeFailed()

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
        microsteps = self._getTowerPositionMicroSteps()
        return self.config.tower_microsteps_to_nm(microsteps)

    @tower_position_nm.setter
    def tower_position_nm(self, position_nm: int) -> None:
        self._towerMoveAbsolute(self.config.nm_to_tower_microsteps(position_nm))

    async def get_tower_sensitivity_async(self) -> int:
        """
        Obtain tower sensitivity

        :return: Sensitivity value
        """

        sensitivity = 0  # use default sensitivity first
        self.updateMotorSensitivity(AxisId.TOWER, sensitivity)
        tries = 3
        while tries > 0:
            try:
                await self.towerSyncWaitAsync()
            except (TowerHomeFailed, TowerEndstopNotReached) as e:
                # if homing failed try different tower homing profiles (only positive values of motor sensitivity)
                sensitivity += 1  # try next motor sensitivity
                tries = 3  # start over with new sensitivity
                if sensitivity >= len(self.towerAdjust["homingFast"]) - 2:
                    raise e

                self.updateMotorSensitivity(AxisId.TOWER, sensitivity)

                continue
            tries -= 1

        return sensitivity

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

    async def verify_tower(self):
        if not self.towerSynced:
            self.setTowerProfile("homingFast")
            await self.towerSyncWaitAsync()
        else:
            self.setTowerProfile("moveFast")
            self.towerToTop()
            while not await self.isTowerOnPositionAsync(retries=3):
                await asyncio.sleep(0.25)

    async def verify_tilt(self):
        if not self.tilt.synced:
            # FIXME MC cant properly home tilt while tower is moving
            while self.isTowerMoving():
                await asyncio.sleep(0.25)
            self.tilt.profile_id = TiltProfile.homingFast
            await self.tilt.sync_wait_async()
        self.tilt.profile_id = TiltProfile.moveFast
        self.tilt.move_up()
        while not self.tilt.on_target_position:
            await asyncio.sleep(0.25)
