# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

from time import sleep
import pydbus

from sl1fw.libPages import page, Page, PageWait


@page
class PageNetwork(Page):
    Name = "network"

    def __init__(self, display):
        super(PageNetwork, self).__init__(display)
        self.pageUI = "network"
        self.pageTitle = N_("Network")
    #enddef


    def fillData(self):
        wificonfig = pydbus.SystemBus().get('cz.prusa3d.sl1.wificonfig')

        aps = {}
        for ap in wificonfig.GetAPs():
            aps[ap['ssid']] = ap

        return {
            'devlist' : self.display.inet.getDevices(),
            'wifi_mode' : wificonfig.WifiMode,
            'client_ssid' : wificonfig.Client['ssid'],
            'client_psk' : wificonfig.Client['psk'],
            'ap_ssid' : wificonfig.Hotspot['ssid'],
            'ap_psk' : wificonfig.Hotspot['psk'],
            'aps' : list(aps.values()),
            'wifi_ssid' : wificonfig.WifiConnectedSSID,
            'wifi_signal' : wificonfig.WifiConnectedSignal,
        }
    #enddef


    def show(self):
        wificonfig = pydbus.SystemBus().get('cz.prusa3d.sl1.wificonfig')
        wificonfig.Scan()
        self.items.update(self.fillData())
        super(PageNetwork, self).show()
    #enddef


    def netChange(self):
        self.showItems(**self.fillData())
    #enddef


    def clientconnectButtonSubmit(self, data):
        self.display.pages['yesno'].setParams(
            yesFce = self.setclient,
            yesParams = { 'ssid': data['client-ssid'], 'psk': data['client-psk'] },
            text = _("Do you really want to set the Wi-fi to client mode?\n\n"
                "It may disconnect the web client."))
        return "yesno"
    #enddef


    def apsetButtonSubmit(self, data):
        self.display.pages['yesno'].setParams(
            yesFce = self.setap,
            yesParams = { 'ssid': data['ap-ssid'], 'psk': data['ap-psk'] },
            text = _("Do you really want to set the Wi-fi to AP mode?\n\n"
                "It may disconnect the web client."))
        return "yesno"
    #enddef


    def wifioffButtonSubmit(self, data):
        self.display.pages['yesno'].setParams(
            yesFce = self.wifioff,
            text = _("Do you really want to turn off the Wi-fi?\n\n"
                "It may disconnect the web client."))
        return "yesno"
    #enddef


    def wifionButtonSubmit(self, data):
        try:
            wificonfig = pydbus.SystemBus().get('cz.prusa3d.sl1.wificonfig')
            wificonfig.StartAP()
            wificonfig.EnableAP()
        except:
            self.logger.error("Setting wifi ap mode (wifi on)")
        #endtry
    #enddef


    def wifioff(self):
        try:
            wificonfig = pydbus.SystemBus().get('cz.prusa3d.sl1.wificonfig')
            wificonfig.StopWifi()
            wificonfig.DisableWifi()
        except:
            self.logger.error("Turning wifi off failed")
        #endtry
        return "_BACK_"
    #enddef


    def setclient(self, ssid, psk):
        pageWait = PageWait(self.display, line1 = _("Setting interface parameters"))
        pageWait.show()

        try:
            wificonfig = pydbus.SystemBus().get('cz.prusa3d.sl1.wificonfig')
            wificonfig.Client = {
                'ssid': ssid,
                'psk': psk,
            }
            wificonfig.StartClient()
            wificonfig.EnableClient()
        except:
            self.logger.exception("Setting wifi client params failed: ssid:%s psk:%s", ssid, psk)
        #endtry

        # Connecting
        pageWait.showItems(line1 = _("Connecting"))
        try:
            wificonfig = pydbus.SystemBus().get('cz.prusa3d.sl1.wificonfig')
            for i in range(1, 10):
                sleep(1)
                if wificonfig.WifiConnectedSSID == ssid:
                    # Connection "ok"
                    return "_BACK_"
                #endfor
            #endfor
        except:
            self.logger.exception("Connection check failed")
        #endtry

        # Connection fail
        self.display.pages['error'].setParams(
                text = _("Connection failed!"))
        return "error"
    #enddef


    def setap(self, ssid, psk):
        pageWait = PageWait(self.display, line1 = _("Setting interface parameters"))
        pageWait.show()

        try:
            wificonfig = pydbus.SystemBus().get('cz.prusa3d.sl1.wificonfig')
            wificonfig.Hotspot = {
                'ssid': ssid,
                'psk': psk,
            }
            wificonfig.StartAP()
            wificonfig.EnableAP()
        except:
            self.logger.error("Setting wifi AP params failed: ssid:%s psk:%s", ssid, psk)
        #endtry

        # Starting AP
        pageWait.showItems(line1 = _("Starting Access Point"))
        for i in range(1, 10):
            sleep(1)
            if wificonfig.WifiMode == "ap":
                # AP "ok"
                return "_BACK_"
            #endfor
        #endfor

        # Connection fail
        self.display.pages['error'].setParams(
                text = _("Starting AP failed!"))
        return "error"
    #enddef

#endclass
