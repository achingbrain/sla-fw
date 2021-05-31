# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from threading import Thread, current_thread
from typing import Callable

from sl1fw.admin.control import AdminControl
from sl1fw.admin.items import AdminLabel, AdminAction
from sl1fw.admin.menu import AdminMenu


class Confirm(AdminMenu):
    def __init__(self, control: AdminControl, target: Callable[[], None], headline="Confirm", text=""):
        super().__init__(control)
        self._target = target
        self._headline = self.add_label(f"<h2>{headline}</h2>")
        self._text = self.add_label(text)
        self.add_back(bold=False)
        self.add_item(AdminAction("<b>Continue</b>", self.cont))

    def cont(self):
        self._control.pop()
        self._target()


class Error(AdminMenu):
    def __init__(self, control: AdminControl, headline="Error", text="", pop=2):
        super().__init__(control)
        self._headline = self.add_label(f"<h2>{headline}</h2>")
        self._text = self.add_label(text)
        self._pop_num = pop
        self.add_item(AdminAction("Ok", self.ok))

    def ok(self):
        self._control.pop(self._pop_num)


class Info(AdminMenu):
    def __init__(self, control: AdminControl, text: str, headline="Info", pop=1):
        super().__init__(control)
        self._headline = self.add_label(f"<h2>{headline}</h2>")
        self._text = self.add_label(text)
        self._pop_num = pop
        self.add_item(AdminAction("Ok", self.ok))

    def ok(self):
        self._control.pop(self._pop_num)


class Wait(AdminMenu):
    def __init__(self, control: AdminControl, body: Callable[[AdminLabel], None], pop=1):
        super().__init__(control)
        self._body = body
        self._thread = Thread(target=self._run)
        self.headline = self.add_label("<h2>Wait...</h2>")
        self.status = self.add_label()
        self._num_pop = pop

    def on_enter(self):
        self._thread.start()

    def on_leave(self):
        if current_thread() != self._thread:
            self._thread.join()

    def _run(self):
        self._body(self.status)
        self._control.pop(self._num_pop, self)
