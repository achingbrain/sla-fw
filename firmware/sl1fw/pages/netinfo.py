# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import pydbus

from sl1fw.pages import page
from sl1fw.libPages import Page


@page
class PageNetInfo(Page):
    Name = "netinfo"

    def __init__(self, display):
        super(PageNetInfo, self).__init__(display)
        self.pageUI = "netinfo"
        self.pageTitle = N_("Network Information")
    #enddef


    def fillData(self):
        wifi = pydbus.SystemBus().get("cz.prusa3d.sl1.wificonfig")

        items = {
            'devlist': self.display.inet.devices,
            'wifi_mode': wifi.WifiMode
        }

        if wifi.WifiMode == "ap":
            try:
                wifiData = wifi.Hotspot
                items['mode'] = "ap"
                items['ap_ssid'] = wifiData['ssid']
                items['ap_psk'] = wifiData['psk']
                items['qr'] = "WIFI:S:%s;T:WPA;P:%s;H:false;" % (wifiData['ssid'], wifiData['psk'])
            except Exception:
                self.logger.exception("wifi setup file exception:")
                items['mode'] = None
                items['text'] = _("Error reading Wi-fi setup!")
            #endtry
        elif wifi.WifiMode == "client" or self.display.inet.ip:
            # client mode
            ip = self.display.inet.ip
            items['mode'] = "client"
            items['client_ip'] = ip
            items['client_hostname'] = self.display.inet.hostname
            items['qr'] = "http://maker:%s@%s/" % (self.octoprintAuth, ip)
            #endif
        else:
            # no internet connection
            items['mode'] = None
            items['text'] = _("Not connected to network")
        #endif
        return items
    #enddef


    def show(self):
        self.items.update(self.fillData())
        super(PageNetInfo, self).show()
    #enddef


    def netChange(self):
        self.showItems(**self.fillData())
    #enddef

#endclass
