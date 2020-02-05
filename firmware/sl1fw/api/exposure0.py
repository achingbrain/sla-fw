# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from time import time
from typing import Any, Dict, List

from deprecated import deprecated
from pydbus.generic import signal

from sl1fw import defines
from sl1fw.api.decorators import dbus_api, DBusObjectPath, auto_dbus, state_checked, range_checked, wrap_variant_dict
from sl1fw.api.states import Exposure0State, Exposure0ProjectState
from sl1fw.exposure_state import ExposureExceptionCode, ExposureException, ExposureWarningCode, ExposureWarning
from sl1fw.libExposure import Exposure


@dbus_api
class Exposure0:
    """
    Exposure dbus interface

    This is first draft. This should contain all data current pages do contain plus some new stuff that should be enough
    to mimic wait pages and similar stuff.

    Most of the functions should be deprecated and replaced by ones returning values in sane units.
    remaining minutes -> expected end timestamp, ...
    """

    __INTERFACE__ = "cz.prusa3d.sl1.exposure0"
    PropertiesChanged = signal()

    @staticmethod
    def dbus_path(instance_id) -> DBusObjectPath:
        return DBusObjectPath(f"/cz/prusa3d/sl1/exposures0/{instance_id}")

    def __init__(self, exposure: Exposure):
        self.exposure = exposure
        self.exposure.change.connect(self._handle_change)

    @auto_dbus
    @state_checked(Exposure0State.CONFIRM)
    def confirm_start(self) -> None:
        """
        Confirm exposure start

        :return: None
        """
        self.exposure.confirm_print_start()

    @auto_dbus
    @state_checked(Exposure0State.CHECK_WARNING)
    def confirm_print_warnings(self) -> None:
        """
        Confirm print continue despite of warnings

        :return: None
        """
        self.exposure.confirm_print_warnings()

    @auto_dbus
    @state_checked(Exposure0State.CHECK_WARNING)
    def reject_print_warnings(self) -> None:
        """
        Escalate warning to error and cancel print

        :return: None
        """
        self.exposure.reject_print_warnings()

    @auto_dbus
    @property
    def exposure_warnings(self) -> List[Dict[str, Any]]:
        """
        Get current list of exposure warnings

        Each exposure warning is represented as dictionary str -> variant
        {
            "code": code , see ExposureWarningCode
            "code_specific_feature1": value1
            "code_specific_feature2": value2
            ...
        }

        :return: List of warning dictionaries
        """
        return [self._process_warning(warning) for warning in self.exposure.warnings]

    @wrap_variant_dict
    def _process_warning(self, warning: ExposureWarning) -> Dict[str, Any]:  # pylint: disable=no-self-use
        if not warning:
            return {
                "code": ExposureWarningCode.NONE.value
            }

        if isinstance(warning, ExposureWarning):
            ret = {
                "code": warning.CODE.value
            }
            ret.update(asdict(warning))
            return ret

        return {
            "code": ExposureWarningCode.UNKNOWN.value
        }

    @auto_dbus
    @property
    @wrap_variant_dict
    def exposure_exception(self) -> Dict[str, Any]:
        """
        Get current exposure exception

        Exposure exception is represented as dictionary str -> variant
        {
            "code": code , see ExposureExceptionCode
            "code_specific_feature1": value1
            "code_specific_feature2": value2
            ...
        }

        :return: Exception dictionary
        """
        if not self.exposure.exception:
            return {
                "code": ExposureExceptionCode.NONE.value
            }

        if isinstance(self.exposure.exception, ExposureException):
            ret = {
                "code": self.exposure.exception.CODE.value
            }
            ret.update(asdict(self.exposure.exception))
            return ret

        return {
            "code": ExposureExceptionCode.UNKNOWN.value
        }

    @auto_dbus
    @property
    def checks_state(self) -> Dict[int, int]:
        """
        State of exposure checks

        :return: Dictionary mapping from check id to state id
        """
        return {check.value: state.value for check, state in self.exposure.check_results.items()}

    @auto_dbus
    @property
    def project_state(self) -> int:
        """
        State of source project data

        :return: Exposure0ProjectState as integer
        """
        return Exposure0ProjectState.from_project(self.exposure.project.state).value

    @auto_dbus
    @property
    def current_layer(self) -> int:
        """
        Layer currently being printed

        :return: Layer number
        """
        return self.exposure.actualLayer

    @auto_dbus
    @property
    def total_layers(self) -> int:
        """
        Total number of layers in the project

        :return:
        """
        return self.exposure.project.totalLayers

    @auto_dbus
    @property
    @deprecated(reason="Use expected_finish_timestamp", action="once")
    def time_remain_min(self) -> int:
        """
        Remaining print time

        :return: Remaining time in minutes
        """
        return self.exposure.countRemainTime()

    @auto_dbus
    @property
    def expected_finish_timestamp(self) -> float:
        """
        Get timestamp of expected print end

        :return: Timestamp as float
        """
        end = datetime.now(tz=timezone.utc) + timedelta(minutes=self.exposure.countRemainTime())
        return end.timestamp()

    @auto_dbus
    @property
    @deprecated(reason="Use print_start_timestamp", action="once")
    def time_elapsed_min(self) -> int:
        """
        Return time spent printing

        :return: Time spent printing in minutes
        """
        return int(round((time() - self.exposure.printStartTime) / 60))

    @auto_dbus
    @property
    def print_start_timestamp(self) -> float:
        """
        Get print start time

        :return: Timestamp
        """
        return self.exposure.printStartTime

    @auto_dbus
    @property
    @deprecated(reason="Use layer_height_first_nm", action="once")
    def layer_height_first_mm(self) -> int:
        """
        Height of the first layer

        :return: Height in millimeters
        """
        return self.exposure.hwConfig.calcMM(self.exposure.project.layerMicroStepsFirst)

    @auto_dbus
    @property
    def layer_height_first_nm(self) -> int:
        """
        Height of the first layer

        :return: Height in nanometers
        """
        return self.exposure.hwConfig.tower_microsteps_to_nm(self.exposure.project.layerMicroStepsFirst)

    @auto_dbus
    @property
    @deprecated(reason="Use layer_height_nm", action="once")
    def layer_height_mm(self) -> int:
        """
        Height of the standard layer

        :return: Height in millimeters
        """
        return self.exposure.hwConfig.calcMM(self.exposure.project.layerMicroSteps)

    @auto_dbus
    @property
    def layer_height_nm(self) -> int:
        """
        Height of the standard layer

        :return: Height in nanometers
        """
        return self.exposure.hwConfig.tower_microsteps_to_nm(self.exposure.project.layerMicroSteps)

    @auto_dbus
    @property
    @deprecated(reason="Use position_nm", action="once")
    def position_mm(self) -> int:
        """
        Current layer position

        :return: Layer position in millimeters
        """
        return self.exposure.hwConfig.calcMM(self.exposure.position)

    @auto_dbus
    @property
    def position_nm(self) -> int:
        """
        Current layer position

        :return: Layer position in nanometers
        """
        return self.exposure.hwConfig.tower_microsteps_to_nm(self.exposure.position)

    @auto_dbus
    @property
    @deprecated(reason="Use total_nm", action="once")
    def total_mm(self) -> int:
        """
        Model height

        :return: Height in millimeters
        """
        return self.exposure.totalHeight

    @auto_dbus
    @property
    def total_nm(self) -> int:
        """
        Model height

        :return: Height in nanometers
        """
        return self.exposure.totalHeight * 1000 * 1000

    @auto_dbus
    @property
    def project_name(self) -> str:
        """
        Name of the project

        :return: Name as string
        """
        return self.exposure.project.name

    @auto_dbus
    @property
    def project_file(self) -> str:
        """
        Full path to the project being printed

        :return: Project file with path
        """
        return self.exposure.project.source

    @auto_dbus
    @property
    def progress(self) -> float:
        """
        Progress percentage

        :return: Percentage 0 - 100
        """
        if self.exposure.in_progress:
            return 100 * (self.exposure.actualLayer - 1) / self.exposure.project.totalLayers
        else:
            return 100

    @auto_dbus
    @property
    def resin_used_ml(self) -> float:
        """
        Amount of resin used

        :return: Volume in milliliters
        """
        return self.exposure.resinCount

    @auto_dbus
    @property
    def resin_remaining_ml(self) -> float:
        """
        Remaining resin in the tank

        :return: Volume in milliliters
        """
        return self.exposure.remain_resin_ml

    @auto_dbus
    @property
    def resin_warn(self) -> bool:
        """
        Whenever the remaining resin has reached warning level

        :return: True if reached, False otherwise
        """
        return self.exposure.warn_resin

    @auto_dbus
    @property
    def resin_low(self) -> bool:
        """
        Whenever the resin has reached forced pause level

        :return: True if reached, False otherwise
        """
        return self.exposure.low_resin

    @auto_dbus
    @property
    def remaining_wait_sec(self) -> int:
        """
        If in waiting state this is number of seconds remaing in wait

        :return: Number of seconds
        """
        return self.exposure.remaining_wait_sec

    @auto_dbus
    @property
    def wait_until_timestamp(self) -> float:
        """
        If in wait state this represents end of wait timestamp

        :return: Timestamp as float
        """
        return (datetime.now(tz=timezone.utc) + timedelta(seconds=self.exposure.remaining_wait_sec)).timestamp()

    @auto_dbus
    @property
    def exposure_end(self) -> float:
        """
        End of current layer exposure

        :return: Timestamp as float
        """
        return self.exposure.exposure_end.timestamp()

    @auto_dbus
    @property
    def state(self) -> int:
        """
        Print job state :class:`.states.Exposure0State`

        :return: State as integer
        """
        return Exposure0State.from_exposure(self.exposure.state).value

    @auto_dbus
    @state_checked(Exposure0State.PRINTING)
    def up_and_down(self) -> None:
        """
        Do up and down

        :return: None
        """
        self.exposure.doUpAndDown()

    @auto_dbus
    @deprecated(reason="Use cancel method instead")
    @state_checked(Exposure0State.PRINTING)
    def exit_print(self) -> None:
        """
        Cancel print

        :return: None
        """
        self.exposure.cancel()

    @auto_dbus
    @state_checked([Exposure0State.PRINTING, Exposure0State.CHECKS, Exposure0State.CONFIRM, Exposure0State.COVER_OPEN])
    def cancel(self) -> None:
        """
        Cancel print

        :return: None
        """
        self.exposure.cancel()

    @auto_dbus
    @state_checked(Exposure0State.PRINTING)
    def feed_me(self) -> None:
        """
        Start manual feedme

        :return: None
        """
        self.exposure.doFeedMe()

    @auto_dbus
    @state_checked(Exposure0State.FEED_ME)
    def cont(self) -> None:
        """
        Continue print after pause or feedme

        :return: None
        """
        self.exposure.doContinue()

    @auto_dbus
    @state_checked(Exposure0State.FEED_ME)
    def back(self) -> None:
        """
        Do legacy back

        Useful to back manual feedme

        :return: None
        """
        self.exposure.doBack()

    @property
    def exposure_time_ms(self) -> int:
        return int(self.exposure.project.expTime * 1000)

    @auto_dbus
    @exposure_time_ms.setter
    @range_checked(defines.exposure_time_min_ms, defines.exposure_time_max_ms)
    def exposure_time_ms(self, value: int) -> None:
        self.exposure.project.expTime = value / 1000

    @property
    def exposure_time_first_ms(self) -> int:
        return int(self.exposure.project.expTimeFirst * 1000)

    @auto_dbus
    @exposure_time_first_ms.setter
    @range_checked(defines.exposure_time_first_min_ms, defines.exposure_time_first_max_ms)
    def exposure_time_first_ms(self, value: int) -> None:
        self.exposure.project.expTimeFirst = value / 1000

    @property
    def exposure_time_calibrate_ms(self) -> int:
        return int(self.exposure.project.calibrateTime * 1000)

    @auto_dbus
    @exposure_time_calibrate_ms.setter
    # @range_checked(defines.exposure_time_calibrate_min_ms, defines.exposure_time_calibrate_max_ms)
    def exposure_time_calibrate_ms(self, value: int) -> None:
        self.exposure.project.calibrateTime = value / 1000

    _CHANGE_MAP = {
        "state": {"state"},
        "actualLayer": {"current_layer", "progress", "time_remain_min", "time_elapsed_min", "position_mm",
                        "position_nm", "expected_finish_timestamp"},
        "resinCount": {"resin_used_ml"},
        "remain_resin_ml": {"resin_remaining_ml"},
        "warn_resin": {"resin_warn"},
        "low_resin": {"resin_low"},
        "remaining_wait_sec": {"remaining_wait_sec"},
        "exposure_end": {"exposure_end"}
    }

    def _handle_change(self, key: str, _: Any):
        if key in self._CHANGE_MAP:
            for changed in self._CHANGE_MAP[key]:
                self.PropertiesChanged(self.__INTERFACE__, {changed: getattr(self, changed)}, [])
