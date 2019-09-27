# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

from sl1fw.pages import page
from sl1fw.libPages import Page


@page
class PageSysInfo(Page):
    Name = "sysinfo"

    def __init__(self, display):
        super(PageSysInfo, self).__init__(display)
        self.pageUI = "sysinfo"
        self.pageTitle = N_("System Information")
        self.updateDataPeriod = 0.5
        self.checkPowerbutton = False
    #enddef


    def fillData(self):
        return {
            'serial_number': self.display.printer0.serial_number,
            'system_name': self.display.printer0.system_name,
            'system_version': self.display.printer0.system_version,
            'controller_version': self.display.printer0.controller_sw_version,
            'controller_serial': self.display.printer0.controller_serial,
            'api_key': self.display.printer0.api_key,
            'tilt_fast_time': self.display.printer0.tilt_fast_time_sec,
            'tilt_slow_time': self.display.printer0.tilt_slow_time_sec,
            'fans': self.display.printer0.fans,
            'temps': self.display.printer0.temps,
            'cpu_temp': self.display.printer0.cpu_temp,
            'leds': self.display.printer0.leds,
            'devlist': self.display.printer0.devlist,
            'uv_statistics': self.display.printer0.uv_statistics,
            'resin_sensor_state': self.display.printer0.resin_sensor_state,
            'cover_state': self.display.printer0.cover_state,
            'power_switch_state': self.display.printer0.power_switch_state
        }
    #enddef


    def show(self):
        self.display.printer0.enable_resin_sensor(True)
        super(PageSysInfo, self).show()
    #enddef


    def updateData(self):
        self.showItems(**self.fillData())
    #enddef


    def backButtonRelease(self):
        self.display.printer0.enable_resin_sensor(False)
        return super(PageSysInfo, self).backButtonRelease()
    #enddef

#endclass
