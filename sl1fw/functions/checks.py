# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from logging import Logger
from time import sleep
from typing import Callable

from sl1fw import defines
from sl1fw.errors.errors import (
    UVLEDsVoltagesDifferTooMuch,
    UVLEDHeatsinkFailed,
    FanRPMOutOfTestRange,
    ResinFailed,
    TowerAxisCheckFailed,
    TowerBelowSurface,
)
from sl1fw.configs.hw import HwConfig
from sl1fw.libHardware import Hardware
from sl1fw import test_runtime


def get_uv_check_pwms(hw: Hardware):
    if hw.is500khz:
        return [40, 122, 243, 250]  # board rev 0.6c+

    return [31, 94, 188, 219]  # board rev. < 0.6c


def check_uv_leds(hw: Hardware, progress_callback: Callable[[float], None] = None):
    hw.uvLedPwm = 0
    hw.uvLed(True)
    uv_pwms = get_uv_check_pwms(hw)

    diff = 0.55  # [mV] voltages in all rows cannot differ more than this limit
    row1 = list()
    row2 = list()
    row3 = list()
    for i in range(3):
        if progress_callback:
            progress_callback(i / 3)
        hw.uvLedPwm = uv_pwms[i]
        if not test_runtime.testing:
            sleep(5)  # wait to refresh all voltages (board rev. 0.6+)
        volts = list(hw.getVoltages())
        del volts[-1]  # delete power supply voltage
        if max(volts) - min(volts) > diff and not test_runtime.testing:
            hw.uvLed(False)
            raise UVLEDsVoltagesDifferTooMuch()
        row1.append(int(volts[0] * 1000))
        row2.append(int(volts[1] * 1000))
        row3.append(int(volts[2] * 1000))

    return row1, row2, row3


def check_uv_fans(hw: Hardware, hw_config: HwConfig, logger: Logger, progress_callback: Callable[[float], None] = None):
    fan_diff = 200
    hw.startFans()
    rpm = [[], [], []]
    fans_wait_time = defines.fanWizardStabilizeTime + defines.fanStartStopTime

    # set UV LED to max PWM
    hw.uvLedPwm = get_uv_check_pwms(hw)[3]

    uv_temp = hw.getUvLedTemperature()
    for countdown in range(hw_config.uvWarmUpTime, 0, -1):
        if progress_callback:
            progress_callback(1 - countdown / hw_config.uvWarmUpTime)

        uv_temp = hw.getUvLedTemperature()
        if uv_temp > defines.maxUVTemp:
            logger.error("Skipping UV Fan check due to overheat")
            break
        if any(hw.getFansError().values()):
            logger.error("Skipping UV Fan check due to fan failure")
            break

        if fans_wait_time < hw_config.uvWarmUpTime - countdown:
            actual_rpm = hw.getFansRpm()
            for i in hw.fans:
                rpm[i].append(actual_rpm[i])
        sleep(1)
    hw.uvLed(False)

    # evaluate fans data
    avg_rpms = list()
    if not test_runtime.testing:
        fan_error = hw.getFansError()
    else:
        fan_error = {0: False, 1: False, 2: False}

    for i, fan in hw.fans.items():  # iterate over fans
        if len(rpm[i]) == 0:
            rpm[i].append(fan.targetRpm)
        avg_rpm = sum(rpm[i]) / len(rpm[i])
        if not fan.targetRpm - fan_diff <= avg_rpm <= fan.targetRpm + fan_diff or fan_error[i]:
            logger.error("Fans raw RPM: %s", rpm)
            logger.error("Fans error: %s", fan_error)
            logger.error("Fans samples: %s", len(rpm[i]))
            raise (
                FanRPMOutOfTestRange(
                    fan.name,
                    str(min(rpm[i])) + "-" + str(max(rpm[i])) if len(rpm[i]) > 1 else None,
                    round(avg_rpm) if len(rpm[i]) > 1 else None,
                    fan_error,
                )
            )
        avg_rpms.append(avg_rpm)

    # evaluate UV LED data
    if uv_temp > defines.maxUVTemp:
        raise UVLEDHeatsinkFailed(uv_temp)

    return avg_rpms, uv_temp


def resin_sensor(hw: Hardware, hw_config: HwConfig, logger: Logger):
    hw.towerSyncWait()
    hw.setTowerPosition(hw_config.calcMicroSteps(defines.defaultTowerHeight))
    volume_ml = hw.getResinVolume()
    logger.debug("resin volume: %s", volume_ml)
    if (
        not defines.resinWizardMinVolume <= volume_ml <= defines.resinWizardMaxVolume
    ) and not test_runtime.testing:  # to work properly even with loosen rocker bearing
        raise ResinFailed(volume_ml)

    hw.towerSync()
    hw.tiltSyncWait()
    while hw.isTowerMoving():
        sleep(0.25)
    hw.motorsRelease()
    hw.stopFans()

    return volume_ml


def tower_axis(hw: Hardware, hw_config: HwConfig):
    hw.towerSyncWait()
    hw.setTowerPosition(hw.tower_end)
    hw.setTowerProfile("homingFast")
    hw.towerMoveAbsolute(0)
    while hw.isTowerMoving():
        sleep(0.25)

    if hw.getTowerPositionMicroSteps() == 0:
        # stop 10 mm before end-stop to change sensitive profile
        hw.towerMoveAbsolute(hw.tower_end - 8000)
        while hw.isTowerMoving():
            sleep(0.25)

        hw.setTowerProfile("homingSlow")
        hw.towerMoveAbsolute(hw.tower_max)
        while hw.isTowerMoving():
            sleep(0.25)

    position_microsteps = hw.getTowerPositionMicroSteps()
    # MC moves tower by 1024 steps forward in last step of !twho
    if (
        position_microsteps < hw.tower_end or position_microsteps > hw.tower_end + 1024 + 127
    ):  # add tolerance half full-step
        raise TowerAxisCheckFailed(hw_config.tower_microsteps_to_nm(position_microsteps))


def tilt_calib_start(hw: Hardware):
    hw.setTiltProfile("homingFast")
    hw.tiltMoveAbsolute(hw.tilt_calib_start)
    while hw.isTiltMoving():
        sleep(0.25)


def tower_calibrate(hw: Hardware, hw_config: HwConfig, logger: Logger) -> int:
    logger.info("Starting platform calibration")
    hw.setTiltProfile("homingFast")
    hw.setTiltCurrent(defines.tiltCalibCurrent)
    hw.setTowerPosition(0)
    hw.setTowerProfile("homingFast")

    logger.info("Moving platform to above position")
    hw.towerMoveAbsolute(hw.tower_above_surface)
    while hw.isTowerMoving():
        sleep(0.25)

    logger.info("tower position above: %d", hw.getTowerPositionMicroSteps())
    if hw.getTowerPositionMicroSteps() != hw.tower_above_surface:
        logger.error("Platform calibration [above] failed %s != %s",
                     hw.getTowerPositionMicroSteps(), hw.tower_above_surface)
        hw.beepAlarm(3)
        hw.towerSyncWait()
        raise TowerBelowSurface(hw.tower_position_nm)

    logger.info("Moving platform to min position")
    hw.setTowerProfile("homingSlow")
    hw.towerToMin()
    while hw.isTowerMoving():
        sleep(0.25)
    logger.info("tower position min: %d", hw.getTowerPositionMicroSteps())
    if hw.getTowerPositionMicroSteps() <= hw.tower_min:
        logger.error("Platform calibration [min] failed %s != %s",
                     hw.getTowerPositionMicroSteps(), hw.tower_above_surface)
        hw.beepAlarm(3)
        hw.towerSyncWait()
        raise TowerBelowSurface(hw.tower_position_nm)

    logger.debug("Moving tower to calib position x3")
    hw.towerMoveAbsolute(hw.getTowerPositionMicroSteps() + hw.tower_calib_pos * 3)
    while hw.isTowerMoving():
        sleep(0.25)

    logger.debug("Moving tower to min")
    hw.towerToMin()
    while hw.isTowerMoving():
        sleep(0.25)

    logger.debug("Moving tower to calib position")
    hw.towerMoveAbsolute(hw.getTowerPositionMicroSteps() + hw.tower_calib_pos)
    while hw.isTowerMoving():
        sleep(0.25)
    logger.info("tower position: %d", hw.getTowerPositionMicroSteps())
    towerHeight = -hw.getTowerPositionMicroSteps()
    hw_config.towerHeight = towerHeight
    hw.setTowerProfile("homingFast")
    return towerHeight
