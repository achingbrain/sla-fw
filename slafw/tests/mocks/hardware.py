# This file is part of the SLA firmware
# Copyright (C) 2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
from unittest.mock import Mock, AsyncMock, PropertyMock

from PySignal import Signal

from slafw import defines
from slafw.configs.hw import HwConfig
from slafw.hardware.fan import Fan
from slafw.hardware.printer_model import PrinterModel
from slafw.hardware.sl1.uv_led import UvLedSL1
from slafw.tests.mocks.exposure_screen import ExposureScreen
from slafw.tests.mocks.motion_controller import MotionControllerMock


class HardwareMock:
    # pylint: disable = too-many-instance-attributes
    # pylint: disable = no-self-use
    # pylint: disable = too-many-statements
    def __init__(self, config: HwConfig = None,
                 printer_model: PrinterModel = PrinterModel.SL1):
        if config is None:
            config = HwConfig(Path("/tmp/dummyhwconfig.toml"), is_master=True)    # TODO better!
        self.cpuSerialNo = "CZPX0819X009XC00151"
        self.mcSerialNo = "CZPX0619X678XC12345"

        self._tower_position_nm = defines.defaultTowerHeight * 1000 * 1000

        self.config = config
        self.fans = {
            0: Fan("UV LED fan", defines.fanMaxRPM[0], self.config.fan1Rpm, self.config.fan1Enabled, auto_control=True),
            1: Fan("blower fan", defines.fanMaxRPM[1], self.config.fan2Rpm, self.config.fan2Enabled,),
            2: Fan("rear fan", defines.fanMaxRPM[2], self.config.fan3Rpm, self.config.fan3Enabled,),
        }

        self.tower_end_nm = 150_000_000

        self.tower_above_surface_nm = self.tower_end_nm
        self.tower_min_nm = self.tower_end_nm - 1
        self.tower_calib_pos_nm = self.tower_end_nm
        self.mcFwVersion = "1.0.0"
        self.mcBoardRevision = "6c"

        self.exposure_screen = ExposureScreen(printer_model)
        self.white_pixels_threshold = self.exposure_screen.parameters.width_px * self.exposure_screen.parameters.height_px * self.config.limit4fast // 100

        self.led_temp_idx = 0
        self.ambient_temp_idx = 1
        self.getUvLedState = Mock(return_value=(False, 0))
        self._led_stat_s = 6912
        self._display_stat_s = 3600
        self.getMcTemperatures = Mock(return_value=[46.7, 26.1, 44.3, 0])
        self.get_resin_volume_async = AsyncMock(return_value=defines.resinMaxVolume)
        self.get_resin_sensor_position_mm = AsyncMock(return_value=12.8)
        self.tower_to_resin_measurement_start_position = AsyncMock()
        self.towerPositonFailed = Mock(return_value=False)
        self.getFansError = Mock(return_value={0: False, 1: False, 2: False})
        self.getCpuTemperature = Mock(return_value=53.5)

        self.getVoltages = Mock(return_value=[11.203, 11.203, 11.203, 0])
        self.getUvLedTemperature = Mock(return_value=46.7)

        self.getFansRpm = Mock(return_value=[self.config.fan1Rpm, self.config.fan2Rpm, self.config.fan3Rpm,])
        self.isTowerMoving = Mock(return_value=False)
        self.isTowerOnPositionAsync = AsyncMock(return_value=True)

        self.get_tower_sensitivity = Mock(return_value=0)
        self.get_tower_sensitivity_async = AsyncMock(return_value=0)
        self.towerSyncWaitAsync = AsyncMock()
        self.tower_move_absolute_nm_wait_async = AsyncMock()
        self.verify_tilt = AsyncMock()
        self.verify_tower = AsyncMock()

        self.tilt = Mock()
        self.tilt.on_target_position = Mock(return_value=True)
        self.tilt.position = 5000
        self.tilt.moving = False
        self.tilt.homing_status = 0
        self.tilt.sync_wait_async = AsyncMock()
        self.tilt.home_calibrate_wait_async = AsyncMock()
        self.tilt.layer_down_wait_async = AsyncMock()
        self.tilt.stir_resin_async = AsyncMock()

        self.sl1s_booster = Mock()
        self.sl1s_booster.board_serial_no = "FAKE BOOSTER SERIAL"

        self.cover_state_changed = Signal()
        self.uv_led_overheat = False
        self.fans_error_changed = Signal()

        self.mcc = MotionControllerMock.get_6c()
        self.uv_led = UvLedSL1(self.mcc, printer_model)

    tower_position_nm = PropertyMock(return_value=150_000_000)

    def exit(self):
        self.cover_state_changed.clear()

    def getUvStatistics(self):
        return self._led_stat_s, self._display_stat_s

    def clearUvStatistics(self):
        self._led_stat_s = 0

    def clearDisplayStatistics(self):
        self._display_stat_s = 0

    def getPowerswitchState(self):
        return False

    def calcPercVolume(self, _):
        return 42

    def __reduce__(self):
        return (Mock, ())

    def __getattr__(self, name):
        setattr(self, name, Mock())
        return getattr(self, name)
