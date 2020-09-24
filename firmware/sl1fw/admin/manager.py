# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
from collections import deque
from typing import Deque, Optional

from PySignal import Signal

from sl1fw.admin.control import AdminControl
from sl1fw.admin.menu import AdminMenu


class AdminManager(AdminControl):
    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self._menus: Deque[AdminMenu] = deque()
        self.menu_changed = Signal()

    @property
    def current_menu(self) -> Optional[AdminMenu]:
        if self._menus:
            return self._menus[-1]
        return None

    def enter(self, menu: AdminMenu) -> None:
        self._logger.info("Entering admin menu: %s", menu)
        self._menus.append(menu)
        menu.on_enter()
        self.menu_changed.emit()

    def exit(self) -> None:
        self.pop(len(self._menus))

    def pop(self, count=1) -> None:
        for _ in range(count):
            left = self._menus.pop()
            self._logger.info("Levaing admin menu: %s", left)
            left.on_leave()
        if self.current_menu:
            self.current_menu.on_reenter()
        self.menu_changed.emit()

    def root(self) -> None:
        self.pop(len(self._menus) - 1)