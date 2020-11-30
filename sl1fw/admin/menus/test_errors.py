# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import functools

from prusaerrors.shared.codes import Code
from prusaerrors.sl1.codes import Sl1Codes

from sl1fw.admin.control import AdminControl
from sl1fw.admin.items import AdminAction
from sl1fw.admin.menu import AdminMenu
from sl1fw.libPrinter import Printer


class TestErrors(AdminMenu):
    ARGS = {
        "failed_fans_text": '["rear"]',
        "volume_ml": 242,
        "position_nm": 42000000,
        "position": 4242,
        "fan": "rear",
        "rpm": 4242,
        "avg": 2424,
        "fanError": "[True, False, True]",
        "sensor": "ambient",
        "temperature": 42.42,
        "found": 120,
        "allowed": 150,
        "a64": "FAKEA64SERIAL",
        "mc": "FAKEMCSERIAL",
    }

    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)
        self._printer = printer

        self.add_item(AdminAction("Back", self._control.pop))
        self.add_error_items()

    def add_error_items(self):
        for name, code in Sl1Codes.get_codes().items():
            self.add_item(AdminAction(name, functools.partial(self.do_error, code)))

    def do_error(self, code: Code):
        self._printer.display.pages["error"].setParams(code=code.raw_code, params=self.ARGS)
        self._printer.display.forcePage("error")
