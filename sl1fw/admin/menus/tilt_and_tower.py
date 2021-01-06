# This file is part of the SL1 firmware
# Copyright (C) 2021 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later
from time import sleep

from sl1fw.admin.control import AdminControl
from sl1fw.admin.items import AdminAction, AdminLabel
from sl1fw.admin.menus.dialogs import Wait, Error
from sl1fw.admin.safe_menu import SafeAdminMenu
from sl1fw.libPrinter import Printer


class TiltAndTowerMenu(SafeAdminMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)
        self._printer = printer

        self.add_back()

        self.add_item(AdminAction("Tilt home", self.tilt_home))
        self.add_item(AdminAction("Tilt test", self.tilt_test))
        self.add_item(AdminAction("Tilt profiles", self.tilt_profiles))
        self.add_item(AdminAction("Tilt home calib.", self.tilt_home_calib))
        self.add_item(AdminAction("Tower home", self.tower_home))
        self.add_item(AdminAction("Tower test", self.tower_test))
        self.add_item(AdminAction("Tower profiles", self.tower_profiles))
        self.add_item(AdminAction("Tower home calib.", self.tower_home_calib))
        self.add_item(AdminAction("Turn motors off", self.turn_off_motors))
        self.add_item(AdminAction("Tune tilt", self.tune_tilt))
        self.add_item(AdminAction("Tower sensitivity", self.tower_sensitivity))
        self.add_item(AdminAction("Tower offset", self.tower_offset))

    @SafeAdminMenu.safe_call
    def tilt_home(self):
        self._printer.hw.powerLed("warn")
        self._control.enter(Wait(self._control, self._sync_tilt))

    @SafeAdminMenu.safe_call
    def _sync_tilt(self, status: AdminLabel):
        status.set("Tilt home")
        if not self._printer.hw.tiltSyncWait(retries=2):
            self._control.enter(Error(self._control, text="Failed to sync tilt", pop=2))
        self._printer.hw.powerLed("normal")
        status.set("Tilt home done")

    @SafeAdminMenu.safe_call
    def tilt_test(self):
        self._control.enter(Wait(self._control, self._do_tilt_test))

    @SafeAdminMenu.safe_call
    def _do_tilt_test(self, status: AdminLabel):
        self._printer.hw.powerLed("warn")
        status.set("Tilt sync")
        self._sync_tilt(status)
        self._printer.hw.beepEcho()
        sleep(1)
        status.set("Tilt up")
        self._printer.hw.tiltLayerUpWait()
        self._printer.hw.beepEcho()
        sleep(1)
        status.set("Tilt down")
        self._printer.hw.tiltLayerDownWait()
        self._printer.hw.beepEcho()
        sleep(1)
        status.set("Tilt up")
        self._printer.hw.tiltLayerUpWait()
        self._printer.hw.beepEcho()
        self._printer.hw.powerLed("normal")

    @SafeAdminMenu.safe_call
    def tilt_profiles(self):
        self._printer.display.forcePage("tiltprofiles")

    @SafeAdminMenu.safe_call
    def tilt_home_calib(self):
        self.enter(Wait(self._control, self._do_tilt_home_calib))

    @SafeAdminMenu.safe_call
    def _do_tilt_home_calib(self, status: AdminLabel):
        self._printer.hw.powerLed("warn")
        status.set("Tilt home calibration")
        self._printer.hw.tiltHomeCalibrateWait()
        self._printer.hw.motorsRelease()
        self._printer.hw.powerLed("normal")

    @SafeAdminMenu.safe_call
    def tower_home(self):
        self.enter(Wait(self._control, self._sync_tower))

    @SafeAdminMenu.safe_call
    def _sync_tower(self, status: AdminLabel):
        status.set("Tower home")
        if not self._printer.hw.towerSyncWait(retries=2):
            self._control.enter(Error(self._control, text="Failed to sync tower", pop=2))
        self._printer.hw.powerLed("normal")
        status.set("Tower home done")

    @SafeAdminMenu.safe_call
    def tower_test(self):
        self.enter(Wait(self._control, self._do_tower_test))

    @SafeAdminMenu.safe_call
    def _do_tower_test(self, status: AdminLabel):
        self._printer.hw.powerLed("warn")
        status.set("Moving platform to the top")
        self._sync_tower(status)
        status.set("Moving platform to zero")
        self._printer.hw.towerToZero()
        status2 = self.add_label()
        while not self._printer.hw.isTowerOnZero():
            sleep(0.25)
            status2.set(self._printer.hw.getTowerPosition())
        self._printer.hw.powerLed("normal")

    @SafeAdminMenu.safe_call
    def tower_profiles(self):
        self._printer.display.forcePage("towerprofiles")

    @SafeAdminMenu.safe_call
    def tower_home_calib(self):
        self.enter(Wait(self._control, self._do_test_home_calib))

    def _do_test_home_calib(self, status: AdminLabel):
        self._printer.hw.powerLed("warn")
        status.set("Tower home calibration")
        self._printer.hw.towerHomeCalibrateWait()
        self._printer.hw.motorsRelease()
        self._printer.hw.powerLed("normal")

    @SafeAdminMenu.safe_call
    def turn_off_motors(self):
        self._printer.hw.motorsRelease()

    @SafeAdminMenu.safe_call
    def tune_tilt(self):
        self._printer.display.forcePage("tunetilt")

    @SafeAdminMenu.safe_call
    def tower_sensitivity(self):
        self._printer.display.forcePage("towersensitivity")

    @SafeAdminMenu.safe_call
    def tower_offset(self):
        self._printer.display.forcePage("toweroffset")
