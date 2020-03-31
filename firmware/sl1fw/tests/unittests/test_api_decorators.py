# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from typing import List, Dict, Any, Tuple
from unittest import TestCase
from gi.repository import GLib

from sl1fw.api.decorators import wrap_dict_data, python_to_dbus_type


class TestAPIDecorators(TestCase):
    def test_wrap_dict_data(self):
        self.assertEqual(
            {"num": GLib.Variant("i", 5), "str": GLib.Variant("s", "text")}, wrap_dict_data({"num": 5, "str": "text",})
        )

    def test_python_to_dbus_type(self):
        self.assertEqual("i", python_to_dbus_type(int))
        self.assertEqual("d", python_to_dbus_type(float))
        self.assertEqual("b", python_to_dbus_type(bool))
        self.assertEqual("s", python_to_dbus_type(str))
        self.assertEqual("as", python_to_dbus_type(List[str]))
        self.assertEqual("aai", python_to_dbus_type(List[List[int]]))
        self.assertEqual("a{ii}", python_to_dbus_type(Dict[int, int]))
        self.assertEqual("a{sa{si}}", python_to_dbus_type(Dict[str, Dict[str, int]]))
        self.assertEqual("(isi)", python_to_dbus_type(Tuple[int, str, int]))
        self.assertEqual("a(sa{sv})", python_to_dbus_type(List[Tuple[str, Dict[str, Any]]]))
        self.assertEqual("a{sa{sv}}", python_to_dbus_type(Dict[str, Dict[str, Any]]))


if __name__ == "__main__":
    unittest.main()
