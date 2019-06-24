# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import json

from sl1fw import defines
from sl1fw.libPages import page, Page


@page
class PageNetInfo(Page):
    Name = "netinfo"

    def __init__(self, display):
        super(PageNetInfo, self).__init__(display)
        self.pageUI = "netinfo"
        self.pageTitle = N_("Network Information")
    #enddef


    def fillData(self):
        apDeviceName = "ap0"
        items = {}
        devices = self.display.inet.getDevices()
        if devices:
            if apDeviceName in devices:
                # AP mode
                try:
                    with open(defines.wifiSetupFile, "r") as f:
                        wifiData = json.loads(f.read())
                    #endwith
                    ip = devices[apDeviceName]
                    items['mode'] = "ap"
                    items['ap_ssid'] = wifiData['ssid']
                    items['ap_psk'] = wifiData['psk']
                    items['qr'] = "WIFI:S:%s;T:WPA;P:%s;H:false;" % (wifiData['ssid'], wifiData['psk'])
                except Exception:
                    self.logger.exception("wifi setup file exception:")
                    items['mode'] = None
                    items['text'] = _("Error reading Wi-fi setup!")
                #endtry
            else:
                # client mode
                ip = self.display.inet.getIp()
                items['mode'] = "client"
                items['client_ip'] = ip
                items['client_hostname'] = self.display.inet.getHostname()
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
