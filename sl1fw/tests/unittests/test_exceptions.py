# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import inspect
import re
import unittest
from glob import glob
from pathlib import Path

from gi.repository.GLib import Variant
from prusaerrors.sl1.codes import Sl1Codes

import sl1fw
from sl1fw.api.decorators import wrap_dict_data, wrap_exception
from sl1fw.errors import errors, exceptions, warnings
from sl1fw.errors.warnings import AmbientTooHot
from sl1fw.motion_controller.trace import Trace
from sl1fw.states.printer import PrinterState


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
        "failed_fan_names: List[str]": "UV Fan",
        "volume: float": 12.3,
        "volume_ml: float": 12.3,
        "failed_sensors: List[int]": [2],
        "failed_sensor_names: List[str]": ["UV LED temperature"],
        "message: str": "Error occurred",
        "trace: sl1fw.motion_controller.trace.Trace": Trace(10),
        "current_state: enum.Enum": PrinterState.PRINTING,
        "allowed_states: List[enum.Enum]": [PrinterState.PRINTING],
        "ambient_temperature: float": 42,
        "actual_model: str": "Some other printer",
        "actual_variant: str": "Some other variant",
        "printer_variant: str": "default",
        "project_variant: str": "something_else",
        "changes: Dict[str, Tuple[Any, Any]]": {"exposure": (10, 20)},
        "measured_resin_ml: float": 12.3,
        "required_resin_ml: float": 23.4,
        "warning: Warning": AmbientTooHot(ambient_temperature=42.0),
        "name: str": "fan1",
        "rpm: Union[int, NoneType]": 1234,
        "rpm: Optional[int]": 1234,
        "avg: Union[int, NoneType]": 1234,
        "avg: Optional[int]": 1234,
        "fanError: Dict[int, bool]": {0: False, 1: True, 2: False},
        "uv_temp_deg_c: float": 42.42,
        "position_nm: int": 123450,
        "position: int": 12345,
        "tilt_position: Union[int, NoneType]": 5000,
        "tilt_position: Optional[int]": 5000,
        "tower_position_nm: int": 100000000,
        "sn: str": "123456789",
        "min_resin_ml: float": 10,
        "failed_fans_text: str": "[\"UV LED Fan\"]",
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

            wrapped_exception = wrap_exception(instance)
            wrapped_dict = wrap_dict_data(wrapped_exception)
            self.assertIsInstance(wrapped_dict, dict)
            for key, value in wrapped_dict.items():
                self.assertIsInstance(key, str)
                self.assertIsInstance(value, Variant)

    def test_error_codes_dummy(self):
        """This is a stupid test that checks all attempts to use Sl1Codes.UNKNOWN likes are valid. Pylint cannot do
        this for us as Sl1Codes are runtime generated from Yaml source"""

        # This goes through all the source code looking for Sl1Codes usages and checks whenever these are legit.
        root = Path(sl1fw.__file__).parent
        sources = [Path(source) for source in glob(str(root / "**/*.py"), recursive=True)]
        code_pattern = re.compile(r"(?<=Sl1Codes\.)\w+")
        for source in sources:
            text = source.read_text()
            matches = code_pattern.findall(text)
            for match in matches:
                self.assertIn(match, dir(Sl1Codes))


if __name__ == "__main__":
    unittest.main()
