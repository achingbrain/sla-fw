# This file is part of the SL1 firmware
# Copyright (C) 2021 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from prusaerrors.sl1.codes import Sl1Codes

from sl1fw.admin.control import AdminControl
from sl1fw.admin.items import AdminAction
from sl1fw.admin.menu import AdminMenu
from sl1fw.libPrinter import Printer


class TestErrorTypesMenu(AdminMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)
        self._printer = printer

        self.add_back()

        self.add_item(AdminAction("Error-code+float,str", self.error_code_float_str))
        self.add_item(AdminAction("Error-code+int", self.error_code_int))
        self.add_item(AdminAction("Error-no-code", self.error_no_code))
        self.add_item(AdminAction("Error-code", self.error_code))
        self.add_item(AdminAction("Raise exception", self.raise_exception))

    def error_code_float_str(self):
        self._printer.display.pages["error"].setParams(
            code=Sl1Codes.TEMPERATURE_OUT_OF_RANGE.raw_code, params={"sensor": "ambient", "temperature": 42.123456789,}
        )
        self._printer.display.forcePage("error")

    def error_code_int(self):
        self._printer.display.pages["error"].setParams(
            code=Sl1Codes.TILT_AXIS_CHECK_FAILED.raw_code, params={"position": 42}
        )
        self._printer.display.forcePage("error")

    def error_no_code(self):
        self._printer.display.pages["error"].setParams(
            text=_(
                "Tower home check failed!\n\n" "Please contact tech support!\n\n" "Tower profiles need to be changed."
            )
        )
        self._printer.display.forcePage("error")

    def error_code(self):
        self._printer.display.pages["error"].setParams(
            code=Sl1Codes.UNKNOWN.raw_code,
            text=_(
                "Tower home check failed!\n\n" "Please contact tech support!\n\n" "Tower profiles need to be changed."
            ),
        )
        self._printer.display.forcePage("error")

    @staticmethod
    def raise_exception():
        raise Exception("Test problem")
