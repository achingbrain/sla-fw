# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from threading import Thread
from time import sleep

from sl1fw.admin.items import admin_action, admin_int, admin_text
from sl1fw.admin.control import AdminControl
from sl1fw.admin.menu import AdminMenu
from sl1fw.admin.menus.dialogs import Error


class TestMenu(AdminMenu):
    def __init__(self, control: AdminControl):
        super().__init__(control)
        self._a = 42
        self._b = 0
        self._cnt = 0
        self._text = "inital"
        self._run = True

        self._thread = Thread(target=self._runner)
        self._thread.start()

    def on_leave(self):
        self._run = False
        self._thread.join()

    @admin_action
    def back(self):
        self._control.pop()

    @admin_text
    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, value: str):
        self._text = value

    @admin_action
    def print_hello(self):
        # pylint: disable=no-self-use
        print("Hello world")

    @admin_text
    @property
    def long_text(self):
        return "Long text Long text Long text Long text Long text Long text Long text Long text Long text Long text"

    @admin_int()
    @property
    def a(self) -> int:
        return self._a

    @a.setter
    def a(self, value: int) -> None:
        self._a = value

    @admin_int(step=3)
    @property
    def b(self) -> int:
        return self._b

    @b.setter
    def b(self, value: int) -> None:
        self._b = value

    @admin_action
    def test2(self):
        self._control.enter(TestMenu2(self._control))

    @admin_text
    @property
    def formatted_text(self):
        return "<center>Centered</center><br/><h1>Headline</h1>"

    @admin_action
    def exit(self):
        self._control.exit()

    def _runner(self):
        while self._run:
            sleep(0.5)
            self._cnt += 1
            self.text = f"Text: {self._cnt}"
            print(self._cnt)

    @admin_action
    def error(self):
        self._control.enter(Error(self._control, text="Synthetic error", pop=2))


class TestMenu2(AdminMenu):
    @admin_action
    def back(self):
        self._control.pop()
