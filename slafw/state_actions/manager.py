# This file is part of the SLA firmware
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

from slafw import defines
from slafw.api.exposure0 import Exposure0
from slafw.api.wizard0 import Wizard0
from slafw.configs.runtime import RuntimeConfig
from slafw.exposure.exposure import Exposure
from slafw.libHardware import Hardware
from slafw.image.exposure_image import ExposureImage
from slafw.states.wizard import WizardState
from slafw.wizard.wizard import Wizard


class ActionManager:
    MAX_EXPOSURES = 3

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._current_exposure: Optional[Exposure] = None
        self._current_exposure_change_registration = None
        self._exposure_dbus_objects = Queue()
        self._system_bus = SystemBus()
        self.exposure_change = Signal()
        self.wizard_changed = Signal()
        self._exposure_bus_name = None
        self._wizard: Optional[Wizard] = None
        self._wizard_registration = None
        self._wizard_registered_object = None
        self._wizard_dbus_name = None
        self._exited = False

    def new_exposure(
        self, hw: Hardware, exposure_image: ExposureImage, runtime_config: RuntimeConfig, project: str
    ) -> Exposure:
        # Create new exposure object and apply passed settings
        exposure = Exposure(self._get_job_id(), hw, exposure_image, runtime_config)
        self.logger.info("Created new exposure id: %s", exposure.instance_id)
        # Register properties changed signal of the new exposure as current exposure signal source
        path = self._register_exposure(exposure)
        self._register_exposure_signal(path)

        exposure.read_project(project)

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
        self, reference: Exposure, hw: Hardware, exposure_image: ExposureImage, runtime_config: RuntimeConfig
    ):
        exposure = Exposure(self._get_job_id(), hw, exposure_image, runtime_config)
        exposure.read_project(reference.project.path)
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
        registration = self._system_bus.register_object(path, weak_exposure0, exposure0.dbus)  # type: ignore
        self._exposure_dbus_objects.put((exposure0, registration))
        self.logger.info("New exposure registered as: %s", path)

        # Maintain history of exposure registrations
        self._shrink_exposures_to(self.MAX_EXPOSURES)

        return path

    def _shrink_exposures_to(self, limit: int):
        while self._exposure_dbus_objects.qsize() > limit:
            exposure0, registration = self._exposure_dbus_objects.get()
            registration.unregister()
            # TODO: it is not nice to touch pydbus signal internals, we would better fix the library
            # The map holds strong reference to the Exposure0 preventing release of the exposure from RAM.
            del Exposure0.PropertiesChanged.map[exposure0]
            # pylint: disable=no-member
            # type: ignore[attr-defined]
            del Exposure0.exception.map[exposure0]

    @property
    def exposure(self) -> Optional[Exposure]:
        return self._current_exposure

    def start_wizard(self, wizard: Wizard, handle_state_transitions: bool = True) -> Wizard:
        if self._exited:
            raise Exception("Attempt to start wizard after exit")
        if self._wizard and self._wizard.state in WizardState.finished_states():
            self._unregister_wizard()

        if self._wizard:
            raise Exception("Wizard already running")

        self._wizard = wizard
        if handle_state_transitions:
            self._wizard.state_changed.connect(self._on_wizard_state_change)

        # The request_name and register object can be replaced by simpler publish, but publish keeps reference to
        # API object internals preventing it from gargabe collection
        if not self._wizard_dbus_name:
            self._wizard_dbus_name = self._system_bus.request_name(Wizard0.__INTERFACE__)
        self._wizard_registered_object = Wizard0(weakref.proxy(self._wizard))
        weak_wizard0 = weakref.proxy(self._wizard_registered_object)
        # pylint: disable=no-member
        self._wizard_registration = self._system_bus.register_object(
            self._wizard_registered_object.DBUS_PATH, weak_wizard0, self._wizard_registered_object.dbus  # type: ignore
        )

        self._wizard.start()
        return self._wizard

    def _unregister_wizard(self):
        if self._wizard_registration:
            self._wizard_registration.unregister()
            # TODO: it is not nice to touch pydbus signal internals, we would better fix the library
            # The map holds strong reference to the Wizard0 instance preventing release of the wizard from RAM.
            del Wizard0.PropertiesChanged.map[self._wizard_registered_object]
            self._wizard_registration = None
            self._wizard_registered_object = None
        self._wizard = None

    @property
    def wizard(self) -> Optional[Wizard]:
        return self._wizard

    def exit(self):
        self._exited = True
        if self._wizard and self._wizard.state not in WizardState.finished_states():
            self.logger.warning("Force canceling wizard on action manager exit")
            self._wizard.force_cancel()

        self._shrink_exposures_to(0)
        if self._exposure_bus_name:
            self._exposure_bus_name.unown()
        self._unregister_wizard()
        if self._wizard_dbus_name:
            self._wizard_dbus_name.unown()

        # Throw away reference to let exposure garbage collect
        self._current_exposure = None

    def _on_exposure_change(self, __, changed, ___):
        if "state" in changed:
            self.exposure_change.emit()

    def _on_wizard_state_change(self):
        self.wizard_changed.emit()

    def try_cancel_by_path(self, path: str) -> None:
        """
        Cancel exposure if the paths are equals
        This check if there is a exposure is running before delete the file

        :return: None
        raise NotAvailableInState
        """
        exposure = self.exposure
        if exposure and not exposure.canceled and path == exposure.project.path:
            exposure.try_cancel()
