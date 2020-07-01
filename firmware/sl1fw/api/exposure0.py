# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta, timezone
from enum import unique, Enum
from time import time
from typing import Any, Dict, List, Optional

from deprecation import deprecated
from pydbus.generic import signal
from prusaerrors.sl1.codes import Sl1Codes

from sl1fw import defines
from sl1fw.api.decorators import (
    dbus_api,
    DBusObjectPath,
    auto_dbus,
    state_checked,
    range_checked,
    wrap_exception,
    last_error,
    wrap_dict_data)
from sl1fw.errors.warnings import ExposureWarning
from sl1fw.libExposure import Exposure
from sl1fw.project.project import ProjectState
from sl1fw.states.exposure import ExposureState


@unique
class Exposure0State(Enum):
    """
    Exposure state enumeration
    """

    # INIT = 0
    PRINTING = 1
    GOING_UP = 2
    GOING_DOWN = 3
    WAITING = 4
    COVER_OPEN = 5
    FEED_ME = 6
    FAILURE = 7
    STIRRING = 9
    PENDING_ACTION = 10
    FINISHED = 11
    STUCK = 12
    STUCK_RECOVERY = 13
    READING_DATA = 14
    CONFIRM = 15
    CHECKS = 16
    TILTING_DOWN = 19
    CANCELED = 20
    CHECK_WARNING = 23
    DONE = 24

    @staticmethod
    def from_exposure(state: ExposureState) -> Exposure0State:
        return {
            ExposureState.PRINTING: Exposure0State.PRINTING,
            ExposureState.GOING_UP: Exposure0State.GOING_UP,
            ExposureState.GOING_DOWN: Exposure0State.GOING_DOWN,
            ExposureState.WAITING: Exposure0State.WAITING,
            ExposureState.COVER_OPEN: Exposure0State.COVER_OPEN,
            ExposureState.FEED_ME: Exposure0State.FEED_ME,
            ExposureState.FAILURE: Exposure0State.FAILURE,
            ExposureState.STIRRING: Exposure0State.STIRRING,
            ExposureState.PENDING_ACTION: Exposure0State.PENDING_ACTION,
            ExposureState.FINISHED: Exposure0State.FINISHED,
            ExposureState.STUCK: Exposure0State.STUCK,
            ExposureState.STUCK_RECOVERY: Exposure0State.STUCK_RECOVERY,
            ExposureState.READING_DATA: Exposure0State.READING_DATA,
            ExposureState.CONFIRM: Exposure0State.CONFIRM,
            ExposureState.CHECKS: Exposure0State.CHECKS,
            ExposureState.TILTING_DOWN: Exposure0State.TILTING_DOWN,
            ExposureState.CANCELED: Exposure0State.CANCELED,
            ExposureState.CHECK_WARNING: Exposure0State.CHECK_WARNING,
            ExposureState.DONE: Exposure0State.DONE,
        }[state]


@unique
class Exposure0ProjectState(Enum):
    """
    Project configuration state enumeration
    """

    UNINITIALIZED = -1
    OK = 0
    NOT_FOUND = 1
    CANT_READ = 2
    NOT_ENOUGH_LAYERS = 3
    CORRUPTED = 4
    PRINT_DIRECTLY = 5

    @staticmethod
    def from_project(state: ProjectState) -> Exposure0ProjectState:
        return {
            ProjectState.UNINITIALIZED: Exposure0ProjectState.UNINITIALIZED,
            ProjectState.OK: Exposure0ProjectState.OK,
            ProjectState.NOT_FOUND: Exposure0ProjectState.NOT_FOUND,
            ProjectState.CANT_READ: Exposure0ProjectState.CANT_READ,
            ProjectState.NOT_ENOUGH_LAYERS: Exposure0ProjectState.NOT_ENOUGH_LAYERS,
            ProjectState.CORRUPTED: Exposure0ProjectState.CORRUPTED,
            ProjectState.PRINT_DIRECTLY: Exposure0ProjectState.PRINT_DIRECTLY,
        }[state]


@dbus_api
class Exposure0:
    """
    Exposure D-Bus interface

    This is first draft. This should contain all data current pages do contain plus some new stuff that should be enough
    to mimic wait pages and similar stuff.

    Most of the functions should be deprecated and replaced by ones returning values in sane units.
    remaining minutes -> expected end timestamp, ...
    """

    # This class is an API to the exposure process. As the API is a draft it turned out to have many methods. Let's
    # disable the pylint warning about this, but keep in mind to reduce the interface in next API revision.
    # pylint: disable=too-many-public-methods

    __INTERFACE__ = "cz.prusa3d.sl1.exposure0"
    PropertiesChanged = signal()

    @staticmethod
    def dbus_path(instance_id) -> DBusObjectPath:
        return DBusObjectPath(f"/cz/prusa3d/sl1/exposures0/{instance_id}")

    def __init__(self, exposure: Exposure):
        self._last_exception: Optional[Exception] = None
        self.exposure = exposure
        self.exposure.change.connect(self._handle_change)

    @auto_dbus
    @property
    def last_exception(self) -> Dict[str, Any]:
        return wrap_dict_data(wrap_exception(self._last_exception))

    @auto_dbus
    @last_error
    @state_checked(Exposure0State.CONFIRM)
    def confirm_start(self) -> None:
        """
        Confirm exposure start

        :return: None
        """
        self.exposure.confirm_print_start()

    @auto_dbus
    @last_error
    @state_checked(Exposure0State.CHECK_WARNING)
    def confirm_print_warnings(self) -> None:
        """
        Confirm print continue despite of warnings

        :return: None
        """
        self.exposure.confirm_print_warnings()

    @auto_dbus
    @last_error
    @state_checked(Exposure0State.CHECK_WARNING)
    def reject_print_warnings(self) -> None:
        """
        Escalate warning to error and cancel print

        :return: None
        """
        self.exposure.reject_print_warnings()

    @auto_dbus
    @property
    @last_error
    def exposure_warnings(self) -> List[Dict[str, Any]]:
        """
        Get current list of exposure warnings.

        .. seealso:: :meth:`sl1fw.errors.codes.WarningCode`

        Each exposure warning is represented as dictionary str -> variant::

            {
                "code": code
                "code_specific_feature1": value1
                "code_specific_feature2": value2
            }

        :return: List of warning dictionaries
        """
        return [wrap_dict_data(self._process_warning(warning)) for warning in self.exposure.warnings]

    def _process_warning(self, warning: ExposureWarning) -> Dict[str, Any]:  # pylint: disable=no-self-use
        if not warning:
            return {"code": Sl1Codes.NONE.code}

        if isinstance(warning, ExposureWarning):
            ret = {"code": warning.CODE.code}
            if is_dataclass(warning):
                ret.update(asdict(warning))
            return ret

        return {"code": Sl1Codes.UNKNOWN.code}

    @auto_dbus
    @property
    @last_error
    def exposure_exception(self) -> Dict[str, Any]:
        return wrap_dict_data(wrap_exception(self.exposure.exception))

    @auto_dbus
    @property
    @last_error
    def checks_state(self) -> Dict[int, int]:
        """
        State of exposure checks

        :return: Dictionary mapping from check id to state id
        """
        return {check.value: state.value for check, state in self.exposure.check_results.items()}

    @auto_dbus
    @property
    @last_error
    def project_state(self) -> int:
        """
        State of source project data

        :return: Exposure0ProjectState as integer
        """
        return Exposure0ProjectState.from_project(self.exposure.project.state).value

    @auto_dbus
    @property
    @last_error
    def current_layer(self) -> int:
        """
        Layer currently being printed

        :return: Layer number
        """
        return self.exposure.actualLayer

    @auto_dbus
    @property
    @last_error
    def total_layers(self) -> int:
        """
        Total number of layers in the project

        :return:
        """
        return self.exposure.project.totalLayers

    @auto_dbus
    @property
    @last_error
    @deprecated("Use expected_finish_timestamp")
    def time_remain_min(self) -> int:
        """
        Remaining print time

        :return: Remaining time in minutes
        """
        return self.exposure.countRemainTime()

    @auto_dbus
    @property
    @last_error
    def expected_finish_timestamp(self) -> float:
        """
        Get timestamp of expected print end

        :return: Timestamp as float
        """
        end = datetime.now(tz=timezone.utc) + timedelta(minutes=self.exposure.countRemainTime())
        return end.timestamp()

    @auto_dbus
    @property
    @last_error
    @deprecated("Use print_start_timestamp")
    def time_elapsed_min(self) -> int:
        """
        Return time spent printing

        :return: Time spent printing in minutes
        """
        return int(round((time() - self.exposure.printStartTime) / 60))

    @auto_dbus
    @property
    @last_error
    def print_start_timestamp(self) -> float:
        """
        Get print start time

        :return: Timestamp
        """
        return self.exposure.printStartTime

    @auto_dbus
    @property
    @last_error
    @deprecated("Use layer_height_first_nm")
    def layer_height_first_mm(self) -> float:
        """
        Height of the first layer

        :return: Height in millimeters
        """
        return self.exposure.hwConfig.calcMM(self.exposure.project.layerMicroStepsFirst)

    @auto_dbus
    @property
    @last_error
    def layer_height_first_nm(self) -> int:
        """
        Height of the first layer

        :return: Height in nanometers
        """
        return self.exposure.hwConfig.tower_microsteps_to_nm(self.exposure.project.layerMicroStepsFirst)

    @auto_dbus
    @property
    @last_error
    @deprecated("Use layer_height_nm")
    def layer_height_mm(self) -> float:
        """
        Height of the standard layer

        :return: Height in millimeters
        """
        return self.exposure.hwConfig.calcMM(self.exposure.project.layerMicroSteps)

    @auto_dbus
    @property
    @last_error
    def layer_height_nm(self) -> int:
        """
        Height of the standard layer

        :return: Height in nanometers
        """
        return self.exposure.hwConfig.tower_microsteps_to_nm(self.exposure.project.layerMicroSteps)

    @auto_dbus
    @property
    @last_error
    @deprecated("Use position_nm")
    def position_mm(self) -> float:
        """
        Current layer position

        :return: Layer position in millimeters
        """
        return self.exposure.hwConfig.calcMM(self.exposure.position)

    @auto_dbus
    @property
    @last_error
    def position_nm(self) -> int:
        """
        Current layer position

        :return: Layer position in nanometers
        """
        return self.exposure.hwConfig.tower_microsteps_to_nm(self.exposure.position)

    @auto_dbus
    @property
    @last_error
    @deprecated("Use total_nm")
    def total_mm(self) -> float:
        """
        Model height

        :return: Height in millimeters
        """
        return self.exposure.totalHeight

    @auto_dbus
    @property
    @last_error
    def total_nm(self) -> int:
        """
        Model height

        :return: Height in nanometers
        """
        return self.exposure.totalHeight * 1000 * 1000

    @auto_dbus
    @property
    @last_error
    def project_name(self) -> str:
        """
        Name of the project

        :return: Name as string
        """
        return self.exposure.project.name

    @auto_dbus
    @property
    @last_error
    def project_file(self) -> str:
        """
        Full path to the project being printed

        :return: Project file with path
        """
        return str(self.exposure.project.path)

    @auto_dbus
    @property
    @last_error
    def progress(self) -> float:
        """
        Progress percentage

        :return: Percentage 0 - 100
        """
        # TODO: In new API revision report progress as 0-1
        return 100 * self.exposure.progress

    @auto_dbus
    @property
    @last_error
    def resin_used_ml(self) -> float:
        """
        Amount of resin used

        :return: Volume in milliliters
        """
        return self.exposure.resinCount

    @auto_dbus
    @property
    @last_error
    def resin_remaining_ml(self) -> float:
        """
        Remaining resin in the tank

        :return: Volume in milliliters
        """
        if self.exposure.remain_resin_ml:
            return self.exposure.remain_resin_ml
        return -1

    @auto_dbus
    @property
    @last_error
    def resin_measured_ml(self) -> float:
        """
        Amount of resin measured during last measurement

        :return: Resin volume in milliliters, or -1 if not measured yet
        """
        if self.exposure.resinVolume:
            return self.exposure.resinVolume
        return -1

    @auto_dbus
    @property
    @last_error
    def total_resin_required_ml(self) -> float:
        """
        Total resin required to finish the project

        This is project used material plus minimal amount of resin required for the printer to work

        :return: Required resin in milliliters
        """
        return self.exposure.project.usedMaterial + defines.resinMinVolume

    @auto_dbus
    @property
    @last_error
    def total_resin_required_percent(self) -> float:
        """
        Total resin required to finish the project

        Values over 100 mean the tank has to be refilled during the print.

        :return: Required resin in tank percents
        """
        return self.exposure.hw.calcPercVolume(self.exposure.project.usedMaterial + defines.resinMinVolume)

    @auto_dbus
    @property
    @last_error
    def resin_warn(self) -> bool:
        """
        Whenever the remaining resin has reached warning level

        :return: True if reached, False otherwise
        """
        return self.exposure.warn_resin

    @auto_dbus
    @property
    @last_error
    def resin_low(self) -> bool:
        """
        Whenever the resin has reached forced pause level

        :return: True if reached, False otherwise
        """
        return self.exposure.low_resin

    @auto_dbus
    @property
    @last_error
    def remaining_wait_sec(self) -> int:
        """
        If in waiting state this is number of seconds remaing in wait

        :return: Number of seconds
        """
        return self.exposure.remaining_wait_sec

    @auto_dbus
    @property
    @last_error
    def wait_until_timestamp(self) -> float:
        """
        If in wait state this represents end of wait timestamp

        :return: Timestamp as float
        """
        return (datetime.now(tz=timezone.utc) + timedelta(seconds=self.exposure.remaining_wait_sec)).timestamp()

    @auto_dbus
    @property
    @last_error
    def exposure_end(self) -> float:
        """
        End of current layer exposure

        :return: Timestamp as float, or -1 of no layer exposed to UV
        """
        if self.exposure.exposure_end:
            return self.exposure.exposure_end.timestamp()
        return -1

    @auto_dbus
    @property
    @last_error
    def state(self) -> int:
        """
        Print job state :class:`.states.Exposure0State`

        :return: State as integer
        """
        return Exposure0State.from_exposure(self.exposure.state).value

    @auto_dbus
    @last_error
    @state_checked(Exposure0State.PRINTING)
    def up_and_down(self) -> None:
        """
        Do up and down

        :return: None
        """
        self.exposure.doUpAndDown()

    @auto_dbus
    @last_error
    @deprecated("Use cancel method instead")
    @state_checked(Exposure0State.PRINTING)
    def exit_print(self) -> None:
        """
        Cancel print

        :return: None
        """
        self.exposure.cancel()

    @auto_dbus
    @last_error
    @state_checked([Exposure0State.PRINTING, Exposure0State.CHECKS, Exposure0State.CONFIRM, Exposure0State.COVER_OPEN])
    def cancel(self) -> None:
        """
        Cancel print

        :return: None
        """
        self.exposure.cancel()

    @auto_dbus
    @last_error
    @state_checked(Exposure0State.PRINTING)
    def feed_me(self) -> None:
        """
        Start manual feedme

        :return: None
        """
        self.exposure.doFeedMe()

    @auto_dbus
    @last_error
    @state_checked(Exposure0State.FEED_ME)
    def cont(self) -> None:
        """
        Continue print after pause or feedme

        :return: None
        """
        self.exposure.doContinue()

    @auto_dbus
    @last_error
    @state_checked(Exposure0State.FEED_ME)
    def back(self) -> None:
        """
        Do legacy back

        Useful to back manual feedme

        :return: None
        """
        self.exposure.doBack()

    @property
    @last_error
    def exposure_time_ms(self) -> int:
        return int(self.exposure.project.expTime * 1000)

    @auto_dbus
    @exposure_time_ms.setter
    @last_error
    @range_checked(defines.exposure_time_min_ms, defines.exposure_time_max_ms)
    def exposure_time_ms(self, value: int) -> None:
        self.exposure.project.expTime = value / 1000

    @property
    @last_error
    def exposure_time_first_ms(self) -> int:
        return int(self.exposure.project.expTimeFirst * 1000)

    @auto_dbus
    @exposure_time_first_ms.setter
    @last_error
    @range_checked(defines.exposure_time_first_min_ms, defines.exposure_time_first_max_ms)
    def exposure_time_first_ms(self, value: int) -> None:
        self.exposure.project.expTimeFirst = value / 1000

    @property
    @last_error
    def exposure_time_calibrate_ms(self) -> int:
        return int(self.exposure.project.calibrateTime * 1000)

    @auto_dbus
    @exposure_time_calibrate_ms.setter
    @last_error
    # @range_checked(defines.exposure_time_calibrate_min_ms, defines.exposure_time_calibrate_max_ms)
    def exposure_time_calibrate_ms(self, value: int) -> None:
        self.exposure.project.calibrateTime = value / 1000

    @auto_dbus
    @property
    @last_error
    def calibration_regions(self) -> int:
        """
        Number of calibration regions

        Zero regions means the project is not calibration project.

        :return: Number of calibration regions
        """
        return self.exposure.project.calibrateRegions

    _CHANGE_MAP = {
        "state": {"state"},
        "actualLayer": {
            "current_layer",
            "progress",
            "time_remain_min",
            "time_elapsed_min",
            "position_mm",
            "position_nm",
            "expected_finish_timestamp",
        },
        "resinCount": {"resin_used_ml"},
        "remain_resin_ml": {"resin_remaining_ml"},
        "warn_resin": {"resin_warn"},
        "low_resin": {"resin_low"},
        "remaining_wait_sec": {"remaining_wait_sec"},
        "exposure_end": {"exposure_end"},
        "warnings": {"exposure_warnings"},
        "check_results": {"checks_state"},
    }

    def _handle_change(self, key: str, _: Any):
        if key in self._CHANGE_MAP:
            for changed in self._CHANGE_MAP[key]:
                self.PropertiesChanged(self.__INTERFACE__, {changed: getattr(self, changed)}, [])
