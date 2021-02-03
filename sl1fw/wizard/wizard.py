# This file is part of the SL1 firmware
# Copyright (C) 2020-2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import logging
from asyncio import CancelledError
from datetime import datetime
from queue import Queue
from shutil import copyfile
from tempfile import NamedTemporaryFile
from threading import Thread
from typing import Iterable, Optional, Dict, Any

import json as serializer
from PySignal import Signal

from sl1fw import defines
from sl1fw.api.decorators import wrap_exception
from sl1fw.configs.runtime import RuntimeConfig
from sl1fw.errors.errors import WizardNotCancelable, FailedToSerializeWizardData, FailedToSaveWizardData
from sl1fw.errors.exceptions import PrinterException
from sl1fw.errors.warnings import PrinterWarning
from sl1fw.functions.system import FactoryMountedRW
from sl1fw.libHardware import Hardware
from sl1fw.states.wizard import WizardState, WizardCheckState, WizardId
from sl1fw.wizard.actions import UserActionBroker
from sl1fw.wizard.checks.base import Check, WizardCheckType
from sl1fw.wizard.groups.base import CheckGroup


class Wizard(Thread, UserActionBroker):
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-arguments
    def __init__(
        self,
        identifier: WizardId,
        groups: Iterable[CheckGroup],
        hw: Hardware,
        runtime_config: RuntimeConfig,
        cancelable=True,
    ):
        self._logger = logging.getLogger(__name__)
        Thread.__init__(self)
        UserActionBroker.__init__(self, hw)
        self.__state = WizardState.INIT
        self.__cancelable = cancelable
        self.__groups = groups
        self.__identifier = identifier
        self.started_changed = Signal()
        self.state_changed = Signal()
        self.check_states_changed = Signal()
        self.data_changed = Signal()
        self.exception_changed = Signal()
        self.warnings_changed = Signal()
        self.__current_group: Optional[CheckGroup] = None
        self.unstop_result = Queue()
        self._runtime_config = runtime_config
        self.started = datetime.now()

        for check in self.checks:
            check.state_changed.connect(self.check_states_changed.emit)
            check.state_changed.connect(self.state_changed.emit)
            check.exception_changed.connect(self.exception_changed.emit)
            check.warnings_changed.connect(self.warnings_changed.emit)
            check.data_changed.connect(self.data_changed.emit)

        self.states_changed.connect(self.state_changed.emit)

    @property
    def identifier(self) -> WizardId:
        return self.__identifier

    @property
    def state(self) -> WizardState:
        if self.__state not in [WizardState.FAILED, WizardState.CANCELED, WizardState.STOPPED] and self._states:
            return self._states[0].state

        return self.__state

    @state.setter
    def state(self, value: WizardState):
        if value != self.__state:
            self.__state = value
            self.state_changed.emit()

    @property
    def cancelable(self):
        return self.__cancelable

    @property
    def checks(self) -> Iterable[Check]:
        for group in self.__groups:
            for check in group.checks:
                yield check

    @property
    def exception(self) -> Optional[Exception]:
        for check in self.checks:
            if check.exception:
                return check.exception

        return None

    @property
    def warnings(self) -> Iterable[PrinterWarning]:
        for check in self.checks:
            for warning in check.warnings:
                yield warning

    @property
    def check_state(self) -> Dict[WizardCheckType, WizardCheckState]:
        return {check.type: check.state for check in self.checks}

    @property
    def check_data(self) -> Dict[WizardCheckType, Dict[str, Any]]:
        return {check.type: check.data for check in self.checks}

    def run(self):
        self._logger.info("Wizard %s running", type(self).__name__)
        self.state = WizardState.RUNNING
        self.started_changed.emit()
        self.check_states_changed.emit()

        try:
            for group in self.__groups:
                self.__current_group = group
                self.__run_group(group)
                self.__current_group = None
            self._store_data()
        except CancelledError:
            self._logger.debug("Wizard group canceled successfully")
            self.state = WizardState.CANCELED
        except Exception:
            self.state = WizardState.FAILED
            self._store_data()
            raise

        if self.state not in [WizardState.CANCELED, WizardState.FAILED]:
            self.state = WizardState.DONE
        self._logger.info("Wizard %s finished with state %s", type(self).__name__, self.state)

    def cancel(self):
        if not self.cancelable:
            raise WizardNotCancelable()

        self._logger.info("Canceling wizard")

        if self.__current_group:
            self._logger.debug("Canceling running wizard group")
            self.__current_group.cancel()

    def __run_group(self, group: CheckGroup):
        self._logger.debug("Running check group %s", type(group).__name__)
        while True:
            try:
                asyncio.run(group.run(self))
                break
            except (CancelledError, PrinterException):
                self.state = WizardState.STOPPED
                self._logger.exception("Wizard group stopped by exception")
                if not self.unstop_result.get():
                    raise
                self.state = WizardState.RUNNING

    def abort(self):
        self._logger.info("Aborting wizard")
        self.unstop_result.put(False)

    def retry(self):
        self._logger.info("Retrying wizard")
        self.unstop_result.put(True)

    def _get_data(self) -> Dict[str, Any]:
        data = {}
        for group in self.__groups:
            for check in group.checks:
                if check.state == WizardCheckState.SUCCESS:
                    data.update(check.get_result_data())
                elif check.state == WizardCheckState.FAILURE:
                    data[f"{type(check).__name__.lower()}_exception"] = wrap_exception(check.exception)
                else:
                    self._logger.warning("Check %s in state %s during wizard data store", check, check.state)
        return data

    @property
    def name(self) -> str:
        return type(self).__name__.lower()

    @property
    def alt_names(self) -> Iterable[str]:
        return (self.name,)

    @property
    def base_filename(self) -> str:
        return f"{self.name}_data"

    @property
    def data_filename(self) -> str:
        return f"{self.base_filename}.{serializer.__name__}"

    @property
    def history_data_filename(self) -> str:
        return f"{self.name}_data.{self.started.strftime('%Y-%m-%d_%H-%M-%S')}.{serializer.__name__}"

    def _data_present_in_factory(self) -> bool:
        return any([list(defines.factoryMountPoint.glob(name + "*")) for name in self.alt_names])

    def _store_data(self):
        with NamedTemporaryFile(mode="wt", encoding="utf-8") as temp:
            try:
                data = self._get_data()
                self._logger.debug("Wizard data to store: %s", data)
                if not data:
                    self._logger.info("Not saving empty wizard data")
                    return
                serializer.dump(data, temp)
                temp.flush()
            except Exception as exception:
                raise FailedToSerializeWizardData() from exception

            try:
                # Store as current wizard result in factory (in case it is already not present i.e. from factory setup)
                if not self._data_present_in_factory():
                    with FactoryMountedRW():
                        copyfile(temp.name, defines.factoryMountPoint / self.data_filename)
                        copyfile(temp.name, defines.wizardHistoryPathFactory / self.history_data_filename)
                else:
                    # Store as current wizard result in etc
                    copyfile(temp.name, defines.configDir / self.data_filename)
                    copyfile(temp.name, defines.wizardHistoryPath / self.history_data_filename)

            except Exception as exception:
                raise FailedToSaveWizardData() from exception
        self._logger.info("Wizard %s data stored", type(self).__name__)
