# This file is part of the SL1 firmware
# Copyright (C) 2021 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import Mock

from sl1fw import defines
from sl1fw.configs.hw import HwConfig
from sl1fw.libHardware import Fan
from sl1fw.hardware.printer_model import PrinterModel


class Hardware:
    # pylint: disable = too-many-instance-attributes
    def __init__(self, hw_config: HwConfig = None):
        if hw_config is None:
            hw_config = HwConfig()

        self.is500khz = True

        self.cpuSerialNo = "CZPX0819X009XC00151"
        self.mcSerialNo = "CZPX0619X678XC12345"

        self.tilt_position = 5000
        self.tower_position_nm = defines.defaultTowerHeight * 1000 * 1000 * 1000

        self.hw_config = hw_config
        self.fans = {
            0: Fan("UV LED fan", defines.fanMaxRPM[0], self.hw_config.fan1Rpm, self.hw_config.fan1Enabled,),
            1: Fan("blower fan", defines.fanMaxRPM[1], self.hw_config.fan2Rpm, self.hw_config.fan2Enabled,),
            2: Fan("rear fan", defines.fanMaxRPM[2], self.hw_config.fan3Rpm, self.hw_config.fan3Enabled,),
        }

        self.tower_end = self.hw_config.calcMicroSteps(150)

        self.tower_above_surface = self.tower_end
        self.tower_min = self.tower_end - 1
        self.tower_calib_pos = self.tower_end
        self.mcFwVersion = "1.0.0"
        self.mcBoardRevision = "6c"

        self.printer_model = PrinterModel.SL1
        self.exposure_screen.parameters = self.printer_model.exposure_screen_parameters
        self.white_pixels_threshold = self.exposure_screen.parameters.width_px * self.exposure_screen.parameters.height_px * self.hw_config.limit4fast // 100

        self.getUvLedState = Mock(return_value=(False, 0))
        self._led_stat_s = 6912
        self._display_stat_s = 3600
        self.isTiltOnPosition = Mock(return_value=True)
        self.isTiltMoving = Mock(return_value=False)
        self.getMcTemperatures = Mock(return_value=[46.7, 26.1, 0, 0])
        self.getResinVolume = Mock(return_value=defines.resinWizardMaxVolume)
        self.towerPositonFailed = Mock(return_value=False)
        self.getFansError = Mock(return_value={0: False, 1: False, 2: False})
        self.getCpuTemperature = Mock(return_value=53.5)

        self.getTiltPosition = Mock(return_value=0)
        self.getVoltages = Mock(return_value=[11.203, 11.203, 11.203, 0])
        self.getUvLedTemperature = Mock(return_value=46.7)

        self.getFansRpm = Mock(return_value=[self.hw_config.fan1Rpm, self.hw_config.fan2Rpm, self.hw_config.fan3Rpm,])
        self.isTowerMoving = Mock(return_value=False)
        self.getTowerPositionMicroSteps = Mock(return_value=self.tower_end)

    def getUvStatistics(self):
        return self._led_stat_s, self._display_stat_s

    def clearUvStatistics(self):
        self._led_stat_s = 0

    def clearDisplayStatistics(self):
        self._display_stat_s = 0

    def __reduce__(self):
        return (Mock, ())

    def __getattr__(self, name):
        setattr(self, name, Mock())
        return getattr(self, name)
