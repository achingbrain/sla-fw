# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import logging
from abc import ABC, abstractmethod
from asyncio import CancelledError, sleep
from enum import unique, Enum
from typing import Optional, List, Iterable, Dict, Any

from PySignal import Signal

from sl1fw.libHardware import Hardware
from sl1fw.states.wizard import WizardCheckState
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.setup import Resource, Configuration


@unique
class WizardCheckType(Enum):
    UNKNOWN = 0

    TOWER_RANGE = 1
    TOWER_HOME = 2
    TILT_RANGE = 3
    TILT_HOME = 4
    DISPLAY = 5
    CALIBRATION = 6
    MUSIC = 7
    UV_LEDS = 8
    UV_FANS = 9
    MOVE_TO_FOAM = 10
    MOVE_TO_TANK = 11
    RESIN_SENSOR = 12
    SERIAL_NUMBER = 20
    TEMPERATURE = 21
    TILT_CALIBRATION_START = 22
    TILT_CALIBRATION = 23
    TOWER_CALIBRATION = 24
    TILT_TIMING = 25
    SYS_INFO = 26
    CALIBRATION_INFO = 27
    ERASE_PROJECTS = 28
    RESET_HOSTNAME = 29
    RESET_API_KEY = 30
    RESET_REMOTE_CONFIG = 31
    RESET_HTTP_DIGEST = 32
    RESET_WIFI = 33
    RESET_TIMEZONE = 34
    RESET_NTP = 35
    RESET_LOCALE = 36
    RESET_UV_CALIBRATION_DATA = 37
    REMOVE_SLICER_PROFILES = 38
    RESET_HW_CONFIG = 39
    ERASE_MC_EEPROM = 40
    RESET_HOMING_PROFILES = 41
    SEND_PRINTER_DATA = 42
    DISABLE_FACTORY = 43
    INITIATE_PACKING_MOVES = 44
    FINISH_PACKING_MOVES = 45
    DISABLE_ACCESS = 46
    UV_METER_PRESENT = 60
    UV_WARMUP = 61
    UV_METER_PLACEMENT = 62
    UV_CALIBRATE_CENTER = 63
    UV_CALIBRATE_EDGE = 64
    UV_CALIBRATION_APPLY_RESULTS = 65
    UV_METER_REMOVED = 66
    TILT_LEVEL = 67


class BaseCheck(ABC):
    # pylint: disable=too-many-instance-attributes
    def __init__(
        self,
        check_type: WizardCheckType,
        configuration: Configuration = Configuration(None, None),
        resources: Iterable[Resource] = (),
    ):
        self._logger = logging.getLogger(__name__)
        self._state = WizardCheckState.WAITING
        self._exception: Optional[Exception] = None
        self._warnings: List[Warning] = []
        self._type = check_type
        self._progress = 0
        self._configuration = configuration
        self._resources = sorted(resources)
        self.state_changed = Signal()
        self.data_changed = Signal()
        self.exception_changed = Signal()
        self.warnings_changed = Signal()

    @property
    def type(self) -> WizardCheckType:
        return self._type

    @property
    def configuration(self) -> Configuration:
        return self._configuration

    @property
    def resources(self) -> Iterable[Resource]:
        return self._resources

    @property
    def state(self) -> WizardCheckState:
        return self._state

    @property
    def progress(self) -> float:
        return self._progress

    @progress.setter
    def progress(self, value: float):
        self._progress = value
        self.data_changed.emit()

    @state.setter
    def state(self, value: WizardCheckState):
        if self._state != value:
            self._state = value
            self.state_changed.emit()
            self.data_changed.emit()

    @property
    def exception(self) -> Optional[Exception]:
        return self._exception

    @exception.setter
    def exception(self, value: Exception):
        self._exception = value
        self.exception_changed.emit()
        self.data_changed.emit()

    @property
    def warnings(self) -> Iterable[Warning]:
        return self._warnings

    def add_warning(self, warning: Warning):
        self._warnings.append(warning)
        self.warnings_changed.emit()

    @property
    def data(self) -> Dict[str, Any]:
        data = {
            "state": self.state,
            "progress": self._progress,
        }
        return data

    async def run(self, locks: Dict[Resource, asyncio.Lock], actions: UserActionBroker):
        self._logger.info("Locking resources: %s", type(self).__name__)
        for resource in self.resources:
            await locks[resource].acquire()
        self._logger.info("Locked resources: %s", type(self).__name__)

        try:
            await sleep(0.1)  # This allows to break asyncio program in case the wizard is canceled
            await self.run_wrapper(actions)
        except CancelledError:
            self._logger.warning("Check canceled")
            self.state = WizardCheckState.CANCELED
            raise
        except Exception as e:
            self._logger.exception("Exception: %s", type(self).__name__)
            self.state = WizardCheckState.FAILURE
            self.exception = e
            raise
        finally:
            self._logger.info("Freeing resources: %s", type(self).__name__)
            for resource in self.resources:
                locks[resource].release()
            self._logger.info("Freed resources: %s", type(self).__name__)

        if not self.warnings:
            self.state = WizardCheckState.SUCCESS
        else:
            self.state = WizardCheckState.WARNING

        self._logger.info("Done: %s", type(self).__name__)

    @abstractmethod
    async def run_wrapper(self, actions: UserActionBroker):
        ...

    @staticmethod
    def get_result_data() -> Dict[str, Any]:
        return {}


class Check(BaseCheck):
    async def run_wrapper(self, actions: UserActionBroker):
        self.state = WizardCheckState.RUNNING
        self._logger.info("Running: %s", type(self).__name__)
        self.progress = 0
        await self.async_task_run(actions)
        self.progress = 1
        self._logger.info("Done: %s", type(self).__name__)

    @abstractmethod
    async def async_task_run(self, actions: UserActionBroker):
        ...


class SyncCheck(BaseCheck):
    async def run_wrapper(self, actions: UserActionBroker):
        loop = asyncio.get_running_loop()
        self._logger.debug("With thread pool executor: %s", type(self).__name__)
        await loop.run_in_executor(actions.sync_executor, self.sync_run_wrapper, actions)
        self._logger.debug("Done with thread pool executor: %s", type(self).__name__)

    def sync_run_wrapper(self, actions: UserActionBroker):
        self.state = WizardCheckState.RUNNING
        self._logger.info("Running: %s", type(self).__name__)
        self.progress = 0
        self.task_run(actions)
        self.progress = 1
        self._logger.info("Done: %s", type(self).__name__)

    @abstractmethod
    def task_run(self, actions: UserActionBroker):
        ...


class DangerousCheckBase:
    """
    Dangerous checks require cover closed during operation
    """

    # pylint: disable = too-few-public-methods

    def __init__(self, hw: Hardware, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._hw = hw

    async def wait_cover_closed(self):
        await asyncio.sleep(0)
        while not self._hw.isCoverVirtuallyClosed():
            await asyncio.sleep(0.5)


class DangerousCheck(DangerousCheckBase, Check, ABC):
    # This is just shortcut to inherit DangerousCheckBase, Check, and ABC
    pass


class SyncDangerousCheck(DangerousCheckBase, SyncCheck, ABC):
    def wait_cover_closed_sync(self):
        asyncio.run(super().wait_cover_closed())
