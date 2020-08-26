# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later


# TODO: Fix following pylint problems
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-arguments

import logging
from queue import Queue
from typing import Optional

from PySignal import Signal
from pydbus import SystemBus

from sl1fw import defines
from sl1fw.api.display_test0 import DisplayTest0, DisplayTest0State
from sl1fw.api.exposure0 import Exposure0
from sl1fw.api.unboxing0 import Unboxing0
from sl1fw.libConfig import HwConfig, RuntimeConfig
from sl1fw.libExposure import Exposure
from sl1fw.libHardware import Hardware
from sl1fw.libScreen import Screen
from sl1fw.state_actions.unboxing import Unboxing


class ActionManager:
    MAX_EXPOSURES = 3

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._current_exposure: Optional[Exposure] = None
        self._current_exposure_change_registration = None
        self._exposure_dbus_objects = Queue()
        self._system_bus = SystemBus()
        self.exposure_change = Signal()
        self.unboxing_change = Signal()
        self.display_test_change = Signal()
        self._exposure_bus_name = None
        self._unboxing: Optional[Unboxing] = None
        self._unboxing_dbus_registration = None
        self._display_test: Optional[DisplayTest0] = None
        self._display_test_registration = None

    def new_exposure(
        self,
        config: HwConfig,
        hw: Hardware,
        screen: Screen,
        runtime_config: RuntimeConfig,
        project: str,
        exp_time_ms: Optional[int] = None,
        exp_time_first_ms: Optional[int] = None,
        exp_time_calibrate_ms: Optional[int] = None,
    ) -> Exposure:
        # Create new exposure object and apply passed settings
        exposure = self._create_exposure(
            config, hw, screen, runtime_config, project, exp_time_ms, exp_time_first_ms, exp_time_calibrate_ms
        )

        path = self._register_exposure(exposure)

        # Register properties changed signal of the new exposure as current exposure signal source
        if self._current_exposure_change_registration:
            self._current_exposure_change_registration.unsubscribe()
        exposure_dbus = self._system_bus.get(Exposure0.__INTERFACE__, path)
        self._current_exposure_change_registration = exposure_dbus.PropertiesChanged.connect(self._on_exposure_change)

        self._current_exposure = exposure
        self.exposure_change.emit()
        return exposure

    def load_exposure(self) -> Optional[Exposure]:
        last_exposure = Exposure.load(self.logger)
        if not last_exposure:
            return None

        self.logger.info("Loaded pickled exposure id: %s", last_exposure.instance_id)
        Exposure.cleanup_last_data(self.logger)
        self._register_exposure(last_exposure)

        self._current_exposure = last_exposure
        self.exposure_change.emit()
        return last_exposure

    def _create_exposure(
        self,
        config: HwConfig,
        hw: Hardware,
        screen: Screen,
        runtime_config: RuntimeConfig,
        project: str,
        exp_time_ms: Optional[int] = None,
        exp_time_first_ms: Optional[int] = None,
        exp_time_calibrate_ms: Optional[int] = None,
    ):
        exposure = Exposure(self._get_job_id(), config, hw, screen, runtime_config, project)
        if exp_time_ms:
            exposure.project.expTime = exp_time_ms / 1000
        if exp_time_first_ms:
            exposure.project.expTimeFirst = exp_time_first_ms / 1000
        if exp_time_calibrate_ms:
            exposure.project.calibrateTime = exp_time_calibrate_ms / 1000

        return exposure

    def _get_job_id(self) -> int:
        try:
            with defines.last_job.open("r") as f:
                job_id = int(f.read()) + 1
        except (ValueError, FileNotFoundError):
            self.logger.info("Failed to load last exposure id, starting from 0")
            job_id = 0
        with defines.last_job.open("w") as f:
            f.write(str(job_id))
        return job_id

    def _register_exposure(self, exposure: Exposure) -> str:
        """
        Register exposure on DBus using the API wrapper.

        :param exposure: Exposure to register
        :return: Registered path
        """
        # Register bus name if not already registered
        if not self._exposure_bus_name:
            self._exposure_bus_name = self._system_bus.request_name(Exposure0.__INTERFACE__)

        path = Exposure0.dbus_path(exposure.instance_id)
        exposure0 = Exposure0(exposure)
        registration = self._system_bus.register_object(path, exposure0, None)
        self._exposure_dbus_objects.put(registration)
        self.logger.info("New exposure registered as: %s", path)

        # Maintain history of exposure registrations
        while self._exposure_dbus_objects.qsize() > self.MAX_EXPOSURES:
            self._exposure_dbus_objects.get().unregister()

        return path

    @property
    def exposure(self) -> Optional[Exposure]:
        return self._current_exposure

    def start_unboxing(self, hw: Hardware, config: HwConfig, kit: Optional[bool] = None):
        if self._unboxing_dbus_registration:
            self._unboxing_dbus_registration.unpublish()

        self._unboxing = Unboxing(hw, config, kit)
        self._unboxing.state_changed.connect(self._on_unboxing_change)
        self._unboxing_dbus_registration = self._system_bus.publish(
            Unboxing0.__INTERFACE__, (Unboxing0.DBUS_PATH, Unboxing0(self._unboxing))
        )
        self._unboxing.start()

    def cleanup_unboxing(self) -> None:
        self._unboxing.join()

    def start_display_test(self, hw: Hardware, hw_config: HwConfig, screen : Screen, runtime_config: RuntimeConfig):
        # Do nothing if display test is already running
        if self._display_test and self._display_test.state != DisplayTest0State.FINISHED:
            return

        # Test is in finished state unregister it
        if self._display_test_registration:
            self._display_test_registration.unpublish()
            self._display_test_registration = None

        # Create new display test
        display_test = DisplayTest0(hw, hw_config, screen, runtime_config)
        display_test.change.connect(self.display_test_change.emit)
        self._display_test_registration = self._system_bus.publish(
            DisplayTest0.__INTERFACE__, (DisplayTest0.DBUS_PATH, display_test)
        )
        self.display_test_change.emit()

    @property
    def unboxing(self) -> Optional[Unboxing]:
        return self._unboxing

    @property
    def display_test(self) -> Optional[DisplayTest0]:
        return self._display_test

    def exit(self):
        while not self._exposure_dbus_objects.empty():
            self._exposure_dbus_objects.get().unregister()
        if self._exposure_bus_name:
            self._exposure_bus_name.unown()
        if self._display_test_registration:
            self._display_test_registration.unpublish()

    def _on_exposure_change(self, __, changed, ___):
        if "state" in changed:
            self.exposure_change.emit()

    def _on_unboxing_change(self):
        self.unboxing_change.emit()
