# This file is part of the SLA firmware
# Copyright (C) 2021 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from threading import Thread
from time import sleep

from slafw.admin.control import AdminControl
from slafw.admin.items import AdminAction, AdminTextValue
from slafw.admin.menu import AdminMenu
from slafw.admin.menus.dialogs import Error, Confirm, Info
from slafw.libPrinter import Printer
from slafw.libUvLedMeterMulti import UvLedMeterMulti
from slafw.hardware.tilt import TiltProfile
from slafw.errors.errors import TiltHomeFailed
from slafw.functions.system import hw_all_off


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
        self._printer.hw.saveUvStatistics()
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
        self._printer.hw.powerLed("warn")
        self.status = "Moving platform to the top..."

        if not self._printer.hw.towerSyncWait(retries=2):
            self._control.enter(Error(self._control, text="Failed to sync tower"))
            return

        self.status = "Homing tilt..."
        try:
            self._printer.hw.tilt.sync_wait()
        except TiltHomeFailed:
            self._control.enter(Error(self._control, text="Failed to sync tilt"))
            return

        self._printer.hw.tilt.profile_id = TiltProfile.moveFast
        self._printer.hw.tilt.move_up_wait()

        self.status = "Measuring...\nDo NOT TOUCH the printer"
        volume = round(self._printer.hw.get_precise_resin_volume_ml())
        self._printer.hw.powerLed("normal")
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
        self._status = "Initializing"
        self._tower = 0
        self._tilt = 0
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
    def tower(self):
        return f"Tower cycles: {self._tower}"

    @tower.setter
    def tower(self, value: int):
        self._tower = value

    @property
    def tilt(self):
        return f"Tilt cycles: {self._tilt}"

    @tilt.setter
    def tilt(self, value: int):
        self._tilt = value

    def _runner(self):
        self.status = "Infinite test"
        tower_counter = 0
        tilt_counter = 0
        tower_status = 0
        tilt_may_move = True
        tower_target_position_nm = 0
        # up = 0
        # above Display = 1
        # down = 3

        self._printer.hw.powerLed("warn")
        self._printer.exposure_image.show_system_image("chess16.png")
        self._printer.hw.startFans()
        self._printer.hw.uvLedPwm = self._printer.hw.config.uvPwm
        self._printer.hw.uvLed(True)
        self._printer.hw.towerSyncWait()
        self._printer.hw.tilt.sync_wait()
        while self._run:
            if not self._printer.hw.isTowerMoving():
                if tower_status == 0:  # tower moved to top
                    tower_counter += 1
                    self.tower = tower_counter
                    self.logger.info("towerCounter: %d, tiltCounter: %d", tower_counter, tilt_counter)
                    if (tower_counter % 100) == 0:  # save uv statistics every 100 tower cycles
                        self._printer.hw.saveUvStatistics()
                    self._printer.hw.set_tower_position_nm(0)
                    self._printer.hw.setTowerProfile("homingFast")
                    tower_target_position_nm = self._printer.hw.tower_above_surface_nm
                    self._printer.hw.tower_position_nm = tower_target_position_nm
                    tower_status = 1
                elif tower_status == 1:  # tower above the display
                    tilt_may_move = False
                    if self._printer.hw.tilt.on_target_position:
                        tower_status = 2
                        self._printer.hw.tilt.profile_id = TiltProfile.layerMoveSlow
                        self._printer.hw.setTowerProfile("homingSlow")
                        tower_target_position_nm = self._printer.hw.tower_min_nm
                        self._printer.hw.tower_position_nm = tower_target_position_nm
                elif tower_status == 2:
                    tilt_may_move = True
                    tower_target_position_nm = self._printer.hw.tower_end_nm
                    self._printer.hw.tower_position_nm = tower_target_position_nm
                    tower_status = 0
            if not self._printer.hw.tilt.moving:
                # hack to force tilt to move. Needs MC FW fix. Tilt cannot move up when tower moving
                if self._printer.hw.tilt.position < 128:
                    self._printer.hw.towerStop()
                    self._printer.hw.tilt.profile_id = TiltProfile.homingFast
                    self._printer.hw.tilt.move_up()
                    self._printer.hw.setTowerProfile("homingFast")
                    self._printer.hw.tower_position_nm = tower_target_position_nm
                    sleep(1)
                elif tilt_may_move:
                    tilt_counter += 1
                    self.tilt = tilt_counter
                    self._printer.hw.tilt.profile_id = TiltProfile.homingFast
                    self._printer.hw.tilt.sync_wait()
            sleep(0.25)
        self._printer.hw.powerLed("normal")
        hw_all_off(self._printer.hw, self._printer.exposure_image)
