# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from typing import List, Dict, Any, Tuple
from unittest import TestCase
from gi.repository.GLib import Variant

from sl1fw.api.decorators import wrap_dict_data, python_to_dbus_type


class TestWrapDictData(TestCase):
    def test_dict_str_int(self):
        self.assertEqual(
            {"num": Variant("i", 5), "str": Variant("s", "text")}, wrap_dict_data({"num": 5, "str": "text",})
        )

    def test_warnings(self):
        self.assertEqual(
            {"changes": Variant("a{sv}", {"exposure": Variant("(ii)", (10, 9))})},
            wrap_dict_data({"changes": {"exposure": (10, 9)}}),
        )

    def test_constraints(self):
        self.assertEqual(
            {"value": Variant("a{sv}", {"min": Variant("i", 5), "max": Variant("i", 10)})},
            wrap_dict_data({"value": {"min": 5, "max": 10}}),
        )


class TestPythonToDbus(TestCase):
    def test_int(self):
        self.assertEqual("i", python_to_dbus_type(int))

    def test_float(self):
        self.assertEqual("d", python_to_dbus_type(float))

    def test_bool(self):
        self.assertEqual("b", python_to_dbus_type(bool))

    def test_string(self):
        self.assertEqual("s", python_to_dbus_type(str))

    def test_array_string(self):
        self.assertEqual("as", python_to_dbus_type(List[str]))

    def test_list_list_int(self):
        self.assertEqual("aai", python_to_dbus_type(List[List[int]]))

    def test_dict_int_int(self):
        self.assertEqual("a{ii}", python_to_dbus_type(Dict[int, int]))

    def test_dict_str_dict_int_int(self):
        self.assertEqual("a{sa{si}}", python_to_dbus_type(Dict[str, Dict[str, int]]))

    def test_tuple_int_str_int(self):
        self.assertEqual("(isi)", python_to_dbus_type(Tuple[int, str, int]))

    def test_rauc_status(self):
        self.assertEqual("a(sa{sv})", python_to_dbus_type(List[Tuple[str, Dict[str, Any]]]))

    def test_dict_str_dict_str_any(self):
        self.assertEqual("a{sa{sv}}", python_to_dbus_type(Dict[str, Dict[str, Any]]))


if __name__ == "__main__":
    unittest.main()
