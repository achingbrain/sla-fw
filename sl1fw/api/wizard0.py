# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Optional, Any, Dict, List

from pydbus.generic import signal

from sl1fw.api.decorators import (
    dbus_api,
    auto_dbus,
    wrap_dict_data,
    wrap_exception,
    last_error,
    wrap_warning,
    wrap_dict_data_recursive,
)
from sl1fw.wizard.wizard import Wizard


@dbus_api
class Wizard0:
    # pylint: disable = too-many-public-methods
    __INTERFACE__ = "cz.prusa3d.sl1.wizard0"
    DBUS_PATH = "/cz/prusa3d/sl1/wizard0"
    PropertiesChanged = signal()

    def __init__(self, wizard: Wizard):
        self._last_exception: Optional[Exception] = None
        self._wizard = wizard

        wizard.started_changed.connect(self._started_changed)
        wizard.state_changed.connect(self._state_changed)
        wizard.check_states_changed.connect(self._check_states_changed)
        wizard.exception_changed.connect(self._exception_changed)
        wizard.warnings_changed.connect(self._warnings_changed)
        wizard.check_data_changed.connect(self._check_data_changed)
        wizard.data_changed.connect(self._data_changed)

    @auto_dbus
    @property
    def last_exception(self) -> Dict[str, Any]:
        return wrap_dict_data(wrap_exception(self._last_exception))

    @auto_dbus
    @property
    @last_error
    def identifier(self) -> int:
        return self._wizard.identifier.value

    @auto_dbus
    @property
    @last_error
    def state(self) -> int:
        return self._wizard.state.value

    @auto_dbus
    @property
    @last_error
    def check_states(self) -> Dict[int, int]:
        return {check.value: state.value for check, state in self._wizard.check_state.items()}

    @auto_dbus
    @property
    @last_error
    def check_data(self) -> Dict[int, Dict[str, Any]]:
        return {check.value: wrap_dict_data_recursive(data) for check, data in self._wizard.check_data.items()}

    @auto_dbus
    @property
    @last_error
    def check_exception(self) -> Dict[str, Any]:
        return wrap_dict_data(wrap_exception(self._wizard.exception))

    @auto_dbus
    @property
    @last_error
    def check_warnings(self) -> List[Dict[str, Any]]:
        """
        Get current list of warnings.

        Each exposure warning is represented as dictionary str -> Variant::

            {
                "code": code
                "code_specific_feature1": value1
                "code_specific_feature2": value2
            }

        :return: List of warning dictionaries
        """
        return [wrap_dict_data(wrap_warning(warning)) for warning in self._wizard.warnings]

    @auto_dbus
    @property
    @last_error
    def data(self) -> Dict[str, Any]:
        return wrap_dict_data(self._wizard.data)

    @auto_dbus
    @property
    @last_error
    def cancelable(self) -> bool:
        return self._wizard.cancelable

    @auto_dbus
    @last_error
    def cancel(self):
        self._wizard.cancel()

    @auto_dbus
    @last_error
    def retry(self):
        self._wizard.retry()

    @auto_dbus
    @last_error
    def abort(self):
        self._wizard.abort()

    @auto_dbus
    @last_error
    def prepare_wizard_part_1_done(self):
        self._wizard.prepare_wizard_part_1_done()

    @auto_dbus
    @last_error
    def prepare_wizard_part_2_done(self):
        self._wizard.prepare_wizard_part_2_done()

    @auto_dbus
    @last_error
    def prepare_wizard_part_3_done(self):
        self._wizard.prepare_wizard_part_3_done()

    @auto_dbus
    @last_error
    def prepare_calibration_platform_tank_done(self):
        self._wizard.prepare_calibration_platform_tank_done()

    @auto_dbus
    @last_error
    def prepare_calibration_platform_align_done(self):
        self._wizard.prepare_calibration_platform_align_done()

    @auto_dbus
    @last_error
    def prepare_calibration_tilt_align_done(self):
        self._wizard.prepare_calibration_tilt_align_done()

    @auto_dbus
    @last_error
    def prepare_calibration_finish_done(self):
        self._wizard.prepare_calibration_finish_done()

    @auto_dbus
    @last_error
    def show_results_done(self):
        self._wizard.show_results_done()

    @auto_dbus
    @last_error
    def prepare_displaytest_done(self):
        self._wizard.prepare_displaytest_done()

    @auto_dbus
    @last_error
    def report_display(self, result: bool):
        self._wizard.report_display(result)

    @auto_dbus
    @last_error
    def report_audio(self, result: bool):
        self._wizard.report_audio(result)

    @auto_dbus
    @last_error
    def tilt_move(self, direction: int):
        self._wizard.tilt_move(direction)

    @auto_dbus
    @last_error
    def tilt_calibration_done(self):
        self._wizard.tilt_aligned()

    @auto_dbus
    @last_error
    def safety_sticker_removed(self):
        self._wizard.safety_sticker_removed()

    @auto_dbus
    @last_error
    def side_foam_removed(self):
        self._wizard.side_foam_removed()

    @auto_dbus
    @last_error
    def tank_foam_removed(self):
        self._wizard.tank_foam_removed()

    @auto_dbus
    @last_error
    def display_foil_removed(self):
        self._wizard.display_foil_removed()

    @auto_dbus
    @last_error
    def foam_inserted(self):
        self._wizard.foam_inserted()

    @auto_dbus
    @last_error
    def uv_calibration_prepared(self):
        self._wizard.uv_calibration_prepared()

    @auto_dbus
    @last_error
    def uv_meter_placed(self):
        self._wizard.uv_meter_placed()

    @auto_dbus
    @last_error
    def uv_apply_result(self):
        self._wizard.uv_apply_result()

    @auto_dbus
    @last_error
    def uv_discard_results(self):
        self._wizard.uv_discard_results()

    @auto_dbus
    @last_error
    def sl1s_confirm_upgrade(self):
        self._wizard.sl1s_confirm_upgrade()

    @auto_dbus
    @last_error
    def sl1s_reject_upgrade(self):
        self._wizard.sl1s_reject_upgrade()

    def _started_changed(self):
        self.PropertiesChanged(self.__INTERFACE__, {"identifier": self.identifier}, [])
        self.PropertiesChanged(self.__INTERFACE__, {"cancelable": self.cancelable}, [])

    def _state_changed(self):
        self.PropertiesChanged(self.__INTERFACE__, {"state": self.state}, [])

    def _check_states_changed(self):
        self.PropertiesChanged(self.__INTERFACE__, {"check_states": self.check_states}, [])

    def _exception_changed(self):
        self.PropertiesChanged(self.__INTERFACE__, {"check_exception": self.check_exception}, [])

    def _warnings_changed(self):
        self.PropertiesChanged(self.__INTERFACE__, {"check_warnings": self.check_warnings}, [])

    def _check_data_changed(self):
        self.PropertiesChanged(self.__INTERFACE__, {"check_data": self.check_data}, [])

    def _data_changed(self):
        self.PropertiesChanged(self.__INTERFACE__, {"data": self.data}, [])
