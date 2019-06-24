# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

from sl1fw import defines
from sl1fw.libPages import page, Page


@page
class PageSysInfo(Page):
    Name = "sysinfo"

    def __init__(self, display):
        super(PageSysInfo, self).__init__(display)
        self.pageUI = "sysinfo"
        self.pageTitle = N_("System Information")
        self.items.update({
                'serial_number': self.display.hw.cpuSerialNo,
                'system_name': self.display.hwConfig.os.name,
                'system_version': self.display.hwConfig.os.version,
                'firmware_version': defines.swVersion,
                })
        self.updateDataPeriod = 0.5
        self.skip = 11
        self.checkPowerbutton = False
    #enddef


    def show(self):
        self.oldValues = {}
        self.items['controller_version'] = self.display.hw.mcFwVersion
        self.items['controller_serial'] = self.display.hw.mcSerialNo
        self.items['api_key'] = self.octoprintAuth
        self.items['tilt_fast_time'] = self.display.hwConfig.tiltFastTime
        self.items['tilt_slow_time'] = self.display.hwConfig.tiltSlowTime
        self.display.hw.resinSensor(True)
        self.skip = 11
        super(PageSysInfo, self).show()
    #enddef


    def updateData(self):
        items = {}
        if self.skip > 10:
            self._setItem(items, self.oldValues, 'fans', {'fan%d_rpm' % i: v for i, v in enumerate(self.display.hw.getFansRpm())})
            self._setItem(items, self.oldValues, 'temps', {'temp%d_celsius' % i: v for i, v in enumerate(self.display.hw.getMcTemperatures())})
            self._setItem(items, self.oldValues, 'cpu_temp', self.display.hw.getCpuTemperature())
            self._setItem(items, self.oldValues, 'leds', {'led%d_voltage_volt' % i: v for i, v in enumerate(self.display.hw.getVoltages())})
            self._setItem(items, self.oldValues, 'devlist', self.display.inet.getDevices())
            self._setItem(items, self.oldValues, 'uv_statistics', {'uv_stat%d' % i: v for i, v in enumerate(self.display.hw.getUvStatistics())})   #uv_stats0 - time counter [s] #TODO add uv average current, uv average temperature
            self.skip = 0
        #endif
        self._setItem(items, self.oldValues, 'resin_sensor_state', self.display.hw.getResinSensorState())
        self._setItem(items, self.oldValues, 'cover_state', self.display.hw.isCoverClosed())
        self._setItem(items, self.oldValues, 'power_switch_state', self.display.hw.getPowerswitchState())

        if len(items):
            self.showItems(**items)
        #endif

        self.skip += 1
    #enddef


    def backButtonRelease(self):
        self.display.hw.resinSensor(False)
        return super(PageSysInfo, self).backButtonRelease()
    #enddef

#endclass
