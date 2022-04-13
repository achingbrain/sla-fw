# This file is part of the SLA firmware
# Copyright (C) 2021 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from threading import Thread
from time import sleep

from slafw.admin.control import AdminControl
from slafw.admin.items import AdminAction, AdminTextValue
from slafw.admin.menu import AdminMenu
from slafw.admin.menus.dialogs import Error, Confirm, Info
from slafw.hardware.sl1.tower import TowerProfile
from slafw.libPrinter import Printer
from slafw.libUvLedMeterMulti import UvLedMeterMulti
from slafw.hardware.sl1.tilt import TiltProfile
from slafw.errors.errors import TiltHomeFailed, TowerHomeFailed
from slafw.hardware.power_led_action import WarningAction
from slafw.image.cairo import draw_chess


class TestHardwareMenu(AdminMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)
        self._printer = printer

        self.add_back()
        self.add_items(
            (
                AdminAction("Resin sensor test", self.resin_sensor_test),
                AdminAction("Infinite UV calibrator test", self.infinite_uv_calibrator_test),
                AdminAction("Infinite test", self.infinite_test),
            )
        )

    def resin_sensor_test(self):
        self._control.enter(
            Confirm(
                self._control,
                self.do_resin_sensor_test,
                text="Is there the correct amount of resin in the tank?\n\nIs the tank secured with both screws?",
            )
        )

    def do_resin_sensor_test(self):
        self.enter(ResinSensorTestMenu(self._control, self._printer))

    def infinite_uv_calibrator_test(self):
        self.enter(InfiniteUVCalibratorMenu(self._control))

    def infinite_test(self):
        self._control.enter(
            Confirm(
                self._control,
                self.do_infinite_test,
                text="It is strongly recommended to NOT run this test. This is an infinite routine "
                "which tests durability of exposition display and mechanical parts."
            )
        )

    def do_infinite_test(self):
        self._printer.hw.uv_led.save_usage()
        self.enter(InfiniteTestMenu(self._control, self._printer))


class InfiniteUVCalibratorMenu(AdminMenu):
    # pylint: disable = too-many-instance-attributes
    def __init__(self, control: AdminControl):
        super().__init__(control)

        self.add_items(
            (
                AdminTextValue.from_property(self, InfiniteUVCalibratorMenu.status),
                AdminTextValue.from_property(self, InfiniteUVCalibratorMenu.value),
                AdminTextValue.from_property(self, InfiniteUVCalibratorMenu.iteration),
                AdminAction("Stop", self.stop),
            )
        )

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
        self.status = "Connecting to UV calibrator"
        uvmeter = UvLedMeterMulti()
        connected = False

        cnt = 0
        while self._run:
            self.iteration = f"Successful reads: {cnt}"
            if connected:
                self.status = "Reading UV calibrator data"
                self.logger.info("Reading UV calibrator data")
                if uvmeter.read():
                    uv_mean = uvmeter.get_data().uvMean
                    self.logger.info("Red data: UVMean: %s", uv_mean)
                    self.value = f"Last uvMean = {uv_mean}"
                    cnt += 1
                else:
                    self.status = "UV calibrator disconnected"
                    self.logger.info("UV calibrator disconnected")
                    connected = False
            elif uvmeter.connect():
                self.status = "UV calibrator connected"
                self.logger.info("UV calibrator connected")
                connected = True
        self.status = "Closing UV calibrator"
        self.logger.info("Closing UV calibrator")
        uvmeter.close()


class ResinSensorTestMenu(AdminMenu):
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)

        self._printer = printer
        self._status = "Initializing"
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
        with WarningAction(self._printer.hw.power_led):
            self.status = "Moving platform to the top..."

            try:
                self._printer.hw.tower.sync_wait()
            except TowerHomeFailed:
                self._control.enter(Error(self._control, text="Failed to sync tower"))
                self._printer.hw.motors_release()
                return

            self.status = "Homing tilt..."
            try:
                self._printer.hw.tilt.sync_wait()
            except TiltHomeFailed:
                self._control.enter(Error(self._control, text="Failed to sync tilt"))
                self._printer.hw.motors_release()
                return

            self._printer.hw.tilt.profile_id = TiltProfile.moveFast
            self._printer.hw.tilt.move_ensure(self._printer.hw.config.tiltHeight)

            self.status = "Measuring...\nDo NOT TOUCH the printer"
            volume = round(self._printer.hw.get_precise_resin_volume_ml())

        if not volume:
            self._control.enter(Error(self._control, text="Measurement failed"))
            return

        self._control.enter(Info(self._control, f"Measured resin volume: {volume} ml", pop=2))


class InfiniteTestMenu(AdminMenu):
    # pylint: disable = too-many-instance-attributes
    # pylint: disable = too-many-statements
    def __init__(self, control: AdminControl, printer: Printer):
        super().__init__(control)

        self.add_items(
            (
                AdminTextValue.from_property(self, InfiniteTestMenu.status),
                AdminTextValue.from_property(self, InfiniteTestMenu.tower),
                AdminTextValue.from_property(self, InfiniteTestMenu.tilt),
                AdminAction("Stop", self.stop),
            )
        )
        self._printer = printer
        self._tower_cycles = 0
        self._tilt_cycles = 0
        self._run = True
        self._thread_tilt = Thread(target=self._runner_tilt)
        self._thread_tower = Thread(target=self._runner_tower)
        self._thread_init = Thread(target=self._runner_init)
        self._thread_init.start()

    def on_leave(self):
        self._run = False
        self._thread_tilt.join()
        self._thread_tower.join()

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
    def tower(self):
        return f"Tower cycles: {self._tower_cycles}"

    @tower.setter
    def tower(self, value: int):
        self._tower_cycles = value

    @property
    def tilt(self):
        return f"Tilt cycles: {self._tilt_cycles}"

    @tilt.setter
    def tilt(self, value: int):
        self._tilt_cycles = value

    def _runner_init(self):
        self.status = "Initializing"
        self._printer.hw.exposure_screen.draw_pattern(draw_chess, 16)
        self._printer.hw.start_fans()
        self._printer.hw.uv_led.pwm = self._printer.hw.config.uvPwm
        self._printer.hw.uv_led.on()
        self._printer.hw.tower.sync_wait()
        self._printer.hw.tilt.sync_wait()
        self._printer.hw.tower.profile_id = TowerProfile.homingFast
        self._printer.hw.tilt.profile_id = TiltProfile.homingFast

        self.status = "Running"
        self._thread_tilt.start()
        self._thread_tower.start()

    def _runner_tower(self):
        tower_cycles = 0
        with WarningAction(self._printer.hw.power_led):
            while self._run:
                self._printer.hw.tower.move_ensure(self._printer.hw.tower.resin_end_pos_nm)
                self._printer.hw.tower.sync_wait()
                tower_cycles += 1
                self.tower = tower_cycles
            self._printer.hw_all_off()

    def _runner_tilt(self):
        tilt_cycles = 0
        with WarningAction(self._printer.hw.power_led):
            while self._run:
                self._printer.hw.tilt.move(self._printer.hw.tilt.config_height_position)
                while self._printer.hw.tilt.moving:
                    sleep(0.25)
                self._printer.hw.tilt.move(50)
                while self._printer.hw.tilt.moving:
                    sleep(0.25)
                tilt_cycles += 1
                self.tilt = tilt_cycles
            self._printer.hw_all_off()
