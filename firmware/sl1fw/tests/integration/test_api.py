import unittest
from time import sleep

from sl1fw.api.printer0 import Printer0State
from sl1fw.tests.integration.base import Sl1FwIntegrationTestCaseBase


class TestIntegrationPages(Sl1FwIntegrationTestCaseBase):
    def test_initial_state(self):
        self.assertEqual(Printer0State.IDLE.name, self.printer.printer0.state)
        self.assertEqual("home", self.printer.printer0.current_page)

    def test_homing(self):
        self.printer.printer0.tower_home()
        self.printer.printer0.tilt_home()
        self.printer.printer0.disable_motors()

    def test_control_moves(self):
        self.printer.printer0.tower_move(2)
        sleep(0.1)
        self.printer.printer0.tower_move(0)
        sleep(0.1)
        self.printer.printer0.tower_move(1)
        sleep(0.1)
        self.printer.printer0.tower_move(0)
        sleep(0.1)
        self.printer.printer0.tower_move(-1)
        sleep(0.1)
        self.printer.printer0.tower_move(0)
        sleep(0.1)
        self.printer.printer0.tower_move(-2)
        sleep(0.1)
        self.printer.printer0.tower_move(0)

        # self.printer.printer0.tilt_move(2)
        # sleep(0.1)
        # self.printer.printer0.tilt_move(0)
        # sleep(0.1)
        # self.printer.printer0.tilt_move(1)
        # sleep(0.1)
        # self.printer.printer0.tilt_move(0)
        # sleep(0.1)
        # self.printer.printer0.tilt_move(-1)
        # sleep(0.1)
        # self.printer.printer0.tilt_move(0)
        # sleep(0.1)
        # self.printer.printer0.tilt_move(-2)
        # sleep(0.1)
        # self.printer.printer0.tilt_move(0)

    def test_absolute_moves(self):
        self.printer.printer0.tower_home()
        initial = self.printer.printer0.tower_position_nm
        offset = 12500
        self.printer.printer0.tower_position_nm += offset
        for i in range(1, 30):
            sleep(0.1)
            if self.printer.printer0.tower_position_nm == initial + offset:
                break
        self.assertAlmostEqual(self.printer.printer0.tower_position_nm, initial + offset, 12500)

        self.printer.printer0.tilt_home()
        initial = self.printer.printer0.tilt_position
        offset = 12500
        self.printer.printer0.tilt_position += offset
        for i in range(1, 30):
            sleep(0.1)
            if self.printer.printer0.tilt_position == initial + offset:
                break
        self.assertAlmostEqual(self.printer.printer0.tilt_position, initial + offset, 12500)

        # self.printer.printer0.get_projects()
        # self.printer.printer0.get_firmwares()

    def test_info_read(self):
        self.assertEqual(self.printer.printer0.serial_number, "CZPX0819X009XC00151")
        self.assertGreater(len(self.printer.printer0.system_name), 3)
        self.assertEqual(type(self.printer.printer0.system_name), str)
        self.assertEqual(type(self.printer.printer0.system_version), str)
        self.assertEqual(self.printer.printer0.fans, {'fan0_rpm': 0, 'fan1_rpm': 0, 'fan2_rpm': 0})
        self.assertEqual(self.printer.printer0.temps,
                         {'temp0_celsius': 46.7, 'temp1_celsius': 26.1, 'temp2_celsius': 26.1, 'temp3_celsius': 26.1})
        self.assertEqual(type(self.printer.printer0.cpu_temp), float)
        self.assertEqual(self.printer.printer0.leds,
                         {'led0_voltage_volt': 0.0, 'led1_voltage_volt': 0.0, 'led2_voltage_volt': 0.0,
                          'led3_voltage_volt': 17.776})
        self.assertEqual(self.printer.printer0.devlist, {})
        self.assertTrue('uv_stat0' in self.printer.printer0.uv_statistics)
        self.assertRegex(self.printer.printer0.controller_sw_version, ".*\\..*\\..*")
        self.assertEqual(self.printer.printer0.controller_serial, "CZPX0619X678XC12345")
        self.assertEqual(self.printer.printer0.api_key, "32LF9aXN")
        self.assertEqual(self.printer.printer0.tilt_fast_time_sec, 5.5)
        self.assertEqual(self.printer.printer0.tilt_slow_time_sec, 8.0)
        self.printer.printer0.enable_resin_sensor(True)
        self.printer.printer0.enable_resin_sensor(False)
        self.assertEqual(self.printer.printer0.cover_state, False)
        self.assertEqual(self.printer.printer0.power_switch_state, False)

        # self.printer.printer0.display_test()
        # self.printer.printer0.wizard()
        # self.printer.printer0.update_firmware()
        # self.printer.printer0.save_logs()
        # self.printer.printer0.factory_reset()
        # self.printer.printer0.enter_admin()
        # self.printer.printer0.print()
        # self.printer.printer0.advanced_settings()


if __name__ == '__main__':
    unittest.main()
