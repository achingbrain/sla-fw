# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import functools
from abc import abstractmethod

from sl1fw.admin.control import AdminControl
from sl1fw.admin.items import AdminAction
from sl1fw.admin.menu import AdminMenu
from sl1fw.libPrinter import Printer
from sl1fw.errors.tests import get_classes, get_instance


class TestExceptionMenu(AdminMenu):

    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)
        self._printer = printer

        self.add_back()
        self.add_items(self._get_items())

    @staticmethod
    @abstractmethod
    def _get_classes_list():
        """ implemented in children """

    @staticmethod
    def _sort_classes(data):
        name, cls = data
        return f"{cls.CODE}-{name}"

    def _get_items(self):
        items = []
        for _, cls in sorted(self._get_classes_list(), key=self._sort_classes):
            items.append(AdminAction(f"{cls.CODE.code} - {cls.CODE.title}\n{cls.__name__}", functools.partial(self.do_error, cls)))
        return items

    def do_error(self, cls):
        self._printer.exception_occurred.emit(get_instance(cls))


class TestWarningsMenu(TestExceptionMenu):

    @staticmethod
    def _get_classes_list():
        return get_classes(get_warnings=True)


class TestErrorsMenu(TestExceptionMenu):

    @staticmethod
    def _get_classes_list():
        return get_classes(get_errors=True)
