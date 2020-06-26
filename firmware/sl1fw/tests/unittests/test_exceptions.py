# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import inspect
import unittest

from gi.repository.GLib import Variant

from sl1fw.api.decorators import wrap_dict_data, wrap_exception
from sl1fw.errors import errors, exceptions, warnings
from sl1fw.errors.warnings import AmbientTooHot
from sl1fw.motion_controller.trace import Trace
from sl1fw.states.printer import PrinterState
from sl1fw.states.project import ProjectState


class TestExceptions(unittest.TestCase):
    """
    This automatically tests exception instantiation and DBus wrapping

    Fake args are provided by MOCK_ARGS dictionary. Exceptions are instantiated and processed in the same way as if
    exported to DBus.
    """

    MOCK_ARGS = {
        "url: str": "http://example.com",
        "total_bytes: int": 0,
        "completed_bytes: int": 0,
        "failed_fans: List[int]": [1],
        "project_state: sl1fw.states.project.ProjectState": ProjectState.CANT_READ,
        "volume: float": 12.3,
        "failed_sensors: List[int]": [2],
        "message: str": "Error occurred",
        "trace: sl1fw.motion_controller.trace.Trace": Trace(10),
        "current_state: enum.Enum": PrinterState.PRINTING,
        "allowed_states: List[enum.Enum]": [PrinterState.PRINTING],
        "ambient_temperature: float": 42,
        "actual_model: str": "Some other printer",
        "actual_variant: str": "Some other variant",
        "project_model: str": "Original Prusa SL1",
        "project_variant: str": "SL1",
        "changes: Dict[str, Tuple[Any, Any]]": {"exposure": (10, 20)},
        "measured_resin_ml: float": 12.3,
        "required_resin_ml: float": 23.4,
        "warning: Warning": AmbientTooHot(ambient_temperature=42.0)
    }

    IGNORED_ARGS = {"self", "args", "kwargs"}

    def test_exceptions(self):
        self.do_test(inspect.getmembers(exceptions))

    def test_errors(self):
        self.do_test(inspect.getmembers(errors))

    def test_warning(self):
        self.do_test(inspect.getmembers(warnings))

    def do_test(self, classes):
        for name, cls in classes:
            if not isinstance(cls, type):
                continue

            if not issubclass(cls, Exception):
                continue

            print(f"Testing dbus wrapping for class: {name}")

            parameters = inspect.signature(cls.__init__).parameters
            args = [self.MOCK_ARGS[str(param)] for name, param in parameters.items() if name not in self.IGNORED_ARGS]

            instance = cls(*args)

            wrapped = wrap_dict_data(wrap_exception(instance))
            self.assertIsInstance(wrapped, dict)
            for key, value in wrapped.items():
                self.assertIsInstance(key, str)
                self.assertIsInstance(value, Variant)


if __name__ == "__main__":
    unittest.main()
