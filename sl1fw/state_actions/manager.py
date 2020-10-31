# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# TODO: Fix following pylint problems
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-arguments

import logging
import weakref
from queue import Queue
from typing import Optional

from PySignal import Signal
from pydbus import SystemBus

from sl1fw import defines
from sl1fw.api.display_test0 import DisplayTest0, DisplayTest0State
from sl1fw.api.exposure0 import Exposure0
from sl1fw.api.wizard0 import Wizard0
from sl1fw.libConfig import HwConfig, RuntimeConfig
from sl1fw.libExposure import Exposure
from sl1fw.libHardware import Hardware
from sl1fw.screen.screen import Screen
from sl1fw.states.wizard import WizardState
from sl1fw.wizard.wizard import Wizard


class ActionManager:
    MAX_EXPOSURES = 3

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._current_exposure: Optional[Exposure] = None
        self._current_exposure_change_registration = None
        self._exposure_dbus_objects = Queue()
        self._system_bus = SystemBus()
        self.exposure_change = Signal()
        self.display_test_change = Signal()
        self.wizard_changed = Signal()
        self._exposure_bus_name = None
        self._display_test: Optional[DisplayTest0] = None
        self._display_test_registration = None
        self._wizard: Optional[Wizard0] = None
        self._wizard_registration = None

    def new_exposure(
        self, config: HwConfig, hw: Hardware, screen: Screen, runtime_config: RuntimeConfig, project: str
    ) -> Exposure:
        # Create new exposure object and apply passed settings
        exposure = Exposure(self._get_job_id(), config, hw, screen, runtime_config, project)
        self.logger.info("Created new exposure id: %s", exposure.instance_id)

        # Register properties changed signal of the new exposure as current exposure signal source
        path = self._register_exposure(exposure)
        self._register_exposure_signal(path)

        self._current_exposure = exposure
        self.exposure_change.emit()
        return exposure

    def load_exposure(self, hw: Hardware) -> Optional[Exposure]:
        exposure = Exposure.load(self.logger, hw)
        if not exposure:
            return None

        self.logger.info("Loaded pickled exposure id: %s", exposure.instance_id)
        Exposure.cleanup_last_data(self.logger)
        self._register_exposure(exposure)

        self._current_exposure = exposure
        self.exposure_change.emit()
        return exposure

    def reprint_exposure(
        self, reference: Exposure, config: HwConfig, hw: Hardware, screen: Screen, runtime_config: RuntimeConfig
    ):
        exposure = Exposure(self._get_job_id(), config, hw, screen, runtime_config, reference.project.path)
        exposure.project.set_timings_reference(reference.project)
        self.logger.info("Created reprint exposure id: %s", exposure.instance_id)

        path = self._register_exposure(exposure)
        self._register_exposure_signal(path)

        self._current_exposure = exposure
        self.exposure_change.emit()
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

    def _register_exposure_signal(self, path: str):
        if self._current_exposure_change_registration:
            self._current_exposure_change_registration.unsubscribe()
        exposure_dbus = self._system_bus.get(Exposure0.__INTERFACE__, path)
        self._current_exposure_change_registration = exposure_dbus.PropertiesChanged.connect(self._on_exposure_change)

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
        weak_exposure0 = weakref.proxy(exposure0)
        # pylint: disable=no-member
        registration = self._system_bus.register_object(path, weak_exposure0, exposure0.dbus)
        self._exposure_dbus_objects.put((exposure0, registration))
        self.logger.info("New exposure registered as: %s", path)

        # Maintain history of exposure registrations
        while self._exposure_dbus_objects.qsize() > self.MAX_EXPOSURES:
            exposure0, registration = self._exposure_dbus_objects.get()
            registration.unregister()
            # TODO: it is not nice to touch pydbus signal internals, we would better fix the library
            # The map holds strong reference to the Exposure0 preventing release of the exposure from RAM.
            del Exposure0.PropertiesChanged.map[exposure0]

        return path

    @property
    def exposure(self) -> Optional[Exposure]:
        return self._current_exposure

    def start_display_test(self, hw: Hardware, hw_config: HwConfig, screen: Screen, runtime_config: RuntimeConfig):
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

    def start_wizard(self, wizard: Wizard) -> Wizard:
        if self._wizard and self._wizard.state in WizardState.finished_states():
            self._wizard = None
            self._wizard_registration.unpublish()

        if self._wizard:
            raise Exception("Wizard already running")

        self._wizard = wizard
        self._wizard.state_changed.connect(self._on_wizard_state_change)
        self._wizard_registration = self._system_bus.publish(
            Wizard0.__INTERFACE__, (Wizard0.DBUS_PATH, Wizard0(self._wizard))
        )
        self._wizard.start()
        return self._wizard

    @property
    def display_test(self) -> Optional[DisplayTest0]:
        return self._display_test

    @property
    def wizard(self) -> Optional[Wizard0]:
        return self._wizard

    def exit(self):
        while not self._exposure_dbus_objects.empty():
            _, registration = self._exposure_dbus_objects.get()
            registration.unregister()
        if self._exposure_bus_name:
            self._exposure_bus_name.unown()
        if self._display_test_registration:
            self._display_test_registration.unpublish()
        if self._wizard_registration:
            self._wizard_registration.unpublish()

    def _on_exposure_change(self, __, changed, ___):
        if "state" in changed:
            self.exposure_change.emit()

    def _on_wizard_state_change(self):
        self.wizard_changed.emit()
