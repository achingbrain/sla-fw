# This file is part of the SL1 firmware
# Copyright (C) 2021 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from threading import Thread

from sl1fw.admin.control import AdminControl
from sl1fw.admin.items import AdminAction, AdminTextValue
from sl1fw.admin.menu import AdminMenu
from sl1fw.admin.menus.dialogs import Error, Confirm, Info
from sl1fw.libPrinter import Printer
from sl1fw.pages.infinitetest import PageInfiniteTest
from sl1fw.pages.uvcalibration import PageUvCalibrationBase
from sl1fw.pages.uvfanstest import PageUvFansTest
from sl1fw.hardware.tilt import TiltProfile

class TestHardwareMenu(AdminMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)
        self._printer = printer

        self.add_back()

        self.add_item(AdminAction("Resin sensor test", self.resin_sensor_test))
        self.add_item(AdminAction("UV & Fan test", self.uv_and_fan_test))
        self.add_item(AdminAction("Infinite UV calibrator test", self.infinite_uv_calibrator_test))
        self.add_item(AdminAction("Infinite test", self.infinite_test))

    def resin_sensor_test(self):
        self._control.enter(
            Confirm(
                self._control,
                self.do_resin_sensor_test,
                text="Is there the correct amount of resin in the tank?\n\n" "Is the tank secured with both screws?",
            )
        )

    def do_resin_sensor_test(self):
        self.enter(ResinSensorTestMenu(self._control, self._printer))

    def uv_and_fan_test(self):
        self._printer.display.forcePage(PageUvFansTest.Name)

    def infinite_uv_calibrator_test(self):
        self.enter(InfiniteUVCalibratorMenu(self._control))

    def infinite_test(self):
        self._printer.hw.saveUvStatistics()
        self._printer.display.forcePage(PageInfiniteTest.Name)


class InfiniteUVCalibratorMenu(AdminMenu):
    # pylint: disable = too-many-instance-attributes
    def __init__(self, control: AdminControl):
        super().__init__(control)

        self.add_item(AdminTextValue.from_property(self, InfiniteUVCalibratorMenu.status))
        self.add_item(AdminTextValue.from_property(self, InfiniteUVCalibratorMenu.value))
        self.add_item(AdminTextValue.from_property(self, InfiniteUVCalibratorMenu.iteration))
        self.add_item(AdminAction("Stop", self.stop))

        self._status = "Initializing"
        self._iteration = ""
        self._value = ""
        self._run = True
        self._thread = Thread(target=self._runner)
        self._thread.start()

    def on_leave(self):
        self._run = False
        self._thread.join()

    def stop(self):
        self.status = "Waiting for test thread to join"
        self.on_leave()
        self._control.pop()

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value: str):
        self._status = value

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value: str):
        self._value = value

    @property
    def iteration(self):
        return self._iteration

    @iteration.setter
    def iteration(self, value: str):
        self._iteration = value

    def _runner(self):
        self.status = "Running infinite UV calibrator test"

        cnt = 0
        while self._run:
            cnt += 1
            self.iteration = f"Iteration: {cnt}"
            self.status = "Connecting UV calibrator"
            self.logger.info("Connecting UV calibrator")
            if not PageUvCalibrationBase.uvmeter.connect():
                self._control.enter(Error(self._control, text="Failed to connect UV calibrator", pop=2))

            for _ in range(5):
                self.logger.info("Reading UV calibrator data")
                self.status = "Reading data"
                if not PageUvCalibrationBase.uvmeter.read():
                    self._control.enter(Error(self._control, text="Failed to read UV calibrator data", pop=2))

                uv_mean = PageUvCalibrationBase.uvmeter.get_data().uvMean
                self.logger.info("Red data: UVMean: %s", uv_mean)
                self.value = f"Last uvMean = {uv_mean}"

            self.status = "Closing UV calibrator"
            PageUvCalibrationBase.uvmeter.close()


class ResinSensorTestMenu(AdminMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)

        self._printer = printer
        self._status = "Initializing"
        self._iteration = ""
        self._value = ""
        self.add_item(AdminTextValue.from_property(self, ResinSensorTestMenu.status))
        self._thread = Thread(target=self._runner)
        self._thread.start()

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value: str):
        self._status = value

    def _runner(self):
        # TODO: vyzadovat zavreny kryt po celou dobu!
        self._printer.hw.powerLed("warn")
        self.status = "Moving platform to the top..."

        if not self._printer.hw.towerSyncWait(retries=2):
            self._control.enter(Error(self._control, text="Failed to sync tower", pop=2))

        self.status = "Homing tilt..."
        if not self._printer.hw.tilt.sync_wait(retries=2):
            self._control.enter(Error(self._control, text="Failed to sync tilt", pop=2))

        self._printer.hw.tilt.profile_id = TiltProfile.layerMoveSlow
        self._printer.hw.tilt.move_up_wait()

        self.status = "Measuring...\nDo NOT TOUCH the printer"
        volume = self._printer.hw.get_precise_resin_volume_ml()
        self._printer.hw.powerLed("normal")
        if not volume:
            self._control.enter(Error(self._control, text="Measurement failed", pop=2))

        self._control.enter(Info(self._control, f"Measured resin volume: {volume} ml", pop=3))
