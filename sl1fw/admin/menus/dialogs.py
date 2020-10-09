# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Callable

from sl1fw.admin.control import AdminControl
from sl1fw.admin.items import admin_action, admin_text
from sl1fw.admin.menu import AdminMenu


class Confirm(AdminMenu):
    def __init__(self, control: AdminControl, target: Callable[[], None], headline="Confirm", text=""):
        super().__init__(control)
        self._target = target
        self._headline = headline
        self._text = text

    @admin_text
    @property
    def header(self):
        return f"<h2>{self._headline}</h2><br/>{self._text}"

    @admin_action
    def back(self):
        self._control.pop()

    @admin_action
    def yes(self):
        self._control.pop()
        self._target()


class Error(AdminMenu):
    def __init__(self, control: AdminControl, headline="Error", text="", pop=2):
        super().__init__(control)
        self._headline = headline
        self._text = text
        self._pop_num = pop

    @admin_text
    @property
    def header(self):
        return f"<h2>{self._headline}</h2><br/>{self._text}"

    @admin_action
    def ok(self):
        self._control.pop(self._pop_num)


class Info(AdminMenu):
    def __init__(self, control: AdminControl, text: str, pop=1):
        super().__init__(control)
        self._text = text
        self._pop_num = pop

    @admin_text
    @property
    def header(self):
        return self._text

    @admin_action
    def ok(self):
        self._control.pop(self._pop_num)
