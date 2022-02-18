import os
from unittest.mock import patch, Mock

from slafw import defines
from slafw.configs.hw import HwConfig
from slafw.errors.errors import MotionControllerWrongFw, MotionControllerException, MotionControllerWrongRevision
from slafw.hardware.hardware_sl1 import HardwareSL1
from slafw.hardware.printer_model import PrinterModel
from slafw.tests.base import SlafwTestCase


class TestLibHardwareConnect(SlafwTestCase):
    def setUp(self) -> None:
        super().setUp()
        defines.cpuSNFile = str(self.SAMPLES_DIR / "nvmem")
        defines.cpuTempFile = str(self.SAMPLES_DIR / "cputemp")
        self.hw_config = HwConfig(file_path=self.SAMPLES_DIR / "hardware.cfg")
        self.hw = HardwareSL1(self.hw_config, PrinterModel.SL1)

        try:
            self.hw.connect()
            self.hw.start()
        except Exception as exception:
            self.tearDown()
            raise exception

    def tearDown(self) -> None:
        self.hw.exit()
        if os.path.isfile(self.EEPROM_FILE):
            os.remove(self.EEPROM_FILE)
        super().tearDown()

    def test_mcc_connect_ok(self) -> None:
        self.assertIsNone(self.hw.mcc.connect(mc_version_check=False))

    def test_mcc_connect_wrong_version(self) -> None:
        with patch("slafw.defines.reqMcVersion", "INVALID"), self.assertRaises(MotionControllerWrongFw):
            self.hw.mcc.connect(mc_version_check=True)

    def test_mcc_connect_fatal_fail(self) -> None:
        with patch("slafw.motion_controller.controller.MotionController.getStateBits", Mock(return_value={'fatal': 1})):
            with self.assertRaises(MotionControllerException):
                self.hw.mcc.connect(mc_version_check=False)

    def test_mcc_connect_rev_fail(self) -> None:
        with patch(
                "slafw.motion_controller.controller.MotionController._get_board_revision", Mock(return_value=[5, 5])
        ):  # fw rev 5, board rev 5a
            with self.assertRaises(MotionControllerWrongRevision):
                self.hw.mcc.connect(mc_version_check=False)

    def test_mcc_connect_board_rev_fail(self) -> None:
        with patch(
                "slafw.motion_controller.controller.MotionController._get_board_revision", Mock(return_value=[5, 70])
        ):  # fw rev 5, board rev 6c
            with self.assertRaises(MotionControllerWrongFw):
                self.hw.mcc.connect(mc_version_check=False)
