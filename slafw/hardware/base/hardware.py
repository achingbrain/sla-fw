# This file is part of the SLA firmware
# Copyright (C) 2022 Prusa Research a.s - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import logging
import os
import re
from abc import abstractmethod
from functools import cached_property, lru_cache
from time import sleep
from typing import Dict

import bitstring
import pydbus
from PySignal import Signal

from slafw import defines
from slafw.configs.hw import HwConfig
from slafw.hardware.base.display import PrintDisplay
from slafw.hardware.base.exposure_screen import ExposureScreen
from slafw.hardware.base.fan import Fan
from slafw.hardware.base.temp_sensor import TempSensor
from slafw.hardware.base.uv_led import UVLED
from slafw.hardware.power_led import PowerLed
from slafw.hardware.printer_model import PrinterModel
from slafw.hardware.tilt import Tilt


class BaseHardware:
    # pylint: disable = too-many-instance-attributes
    # pylint: disable = too-many-public-methods
    uv_led: UVLED
    display: PrintDisplay
    tilt: Tilt
    uv_led_fan: Fan
    blower_fan: Fan
    rear_fan: Fan
    uv_led_temp: TempSensor
    ambient_temp: TempSensor
    cpu_temp: TempSensor
    exposure_screen: ExposureScreen
    power_led: PowerLed

    def __init__(self, hw_config: HwConfig, printer_model: PrinterModel):
        self.logger = logging.getLogger(__name__)
        self.config = hw_config
        self._printer_model = printer_model

        self.resin_sensor_state_changed = Signal()
        self.cover_state_changed = Signal()
        self.power_button_state_changed = Signal()
        self.mc_sw_version_changed = Signal()
        self.tower_position_changed = Signal()
        self.tilt_position_changed = Signal()

    @cached_property
    def fans(self) -> Dict[int, Fan]:
        return {
            0: self.uv_led_fan,
            1: self.blower_fan,
            2: self.rear_fan,
        }

    def start_fans(self):
        for fan in self.fans.values():
            fan.enabled = True

    def stop_fans(self):
        for fan in self.fans.values():
            fan.enabled = False

    @abstractmethod
    def connect(self):
        """
        connect to MC and init all hw components
        """

    @abstractmethod
    def start(self):
        """
        init default values
        """

    @property
    def cpuSerialNo(self):
        return self.read_cpu_serial()[0]

    @property
    def isKit(self):
        return self.read_cpu_serial()[1]

    @abstractmethod
    def beep(self, frequency_hz: int, length_s: float):
        ...

    def beepEcho(self) -> None:
        self.beep(1800, 0.05)

    def beepRepeat(self, count):
        for _ in range(count):
            self.beep(1800, 0.1)
            sleep(0.5)

    def beepAlarm(self, count):
        for _ in range(count):
            self.beep(1900, 0.05)
            sleep(0.25)

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

    @lru_cache(maxsize=1)
    def read_cpu_serial(self):
        # pylint: disable = too-many-locals
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
                mac_hex = ":".join(re.findall("../../..", mac.hex))
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

    @cached_property
    def emmc_serial(self) -> str:  # pylint: disable = no-self-use
        return defines.emmc_serial_path.read_text().strip()

    @property
    def white_pixels_threshold(self) -> int:
        return (
            self.exposure_screen.parameters.width_px
            * self.exposure_screen.parameters.height_px
            * self.config.limit4fast
            // 100
        )

    @property
    @abstractmethod
    def tower_position_nm(self) -> int:
        ...

    @tower_position_nm.setter
    @abstractmethod
    def tower_position_nm(self, value: int):
        ...

    async def tower_move_absolute_nm_wait_async(self, position_nm: int):
        self.tower_position_nm = position_nm
        while not await self.isTowerOnPositionAsync():
            await asyncio.sleep(0.25)

    def setTowerCurrent(self, current):  # pylint: disable=unused-argument,no-self-use
        return

    def tower_move_absolute_nm_wait(self, position_nm):
        return asyncio.run(self.tower_move_absolute_nm_wait_async(position_nm))

    @abstractmethod
    async def isTowerOnPositionAsync(self, retries: int = 1) -> bool:
        ...

    def isTowerOnPosition(self, retries: int = 1) -> bool:
        return asyncio.run(self.isTowerOnPositionAsync(retries))

    @abstractmethod
    def exit(self):
        ...
