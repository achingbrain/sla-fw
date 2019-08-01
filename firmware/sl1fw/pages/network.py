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
        self.wificonfig = pydbus.SystemBus().get('cz.prusa3d.sl1.wificonfig')
    #enddef


    def fillData(self):
        return {
            'devlist' : self.display.inet.getDevices(),
            'wifi_mode' : wificonfig.WifiMode,
            'client_ssid' : wificonfig.Client['ssid'],  # Deprecated
            'client_psk' : wificonfig.Client['psk'],  # Deprecated
            'ap_ssid' : wificonfig.Hotspot['ssid'],
            'ap_psk' : wificonfig.Hotspot['psk'],
            'aps' : list(aps.values()),
            'wifi_ssid' : wificonfig.WifiConnectedSSID,
            'wifi_signal' : wificonfig.WifiConnectedSignal,
        }
    #enddef


    def show(self):
        self.wificonfig.Scan()
        self.items.update(self.fillData())
        super(PageNetwork, self).show()
    #enddef


    def netChange(self):
        self.showItems(**self.fillData())
    #enddef


    def apsChanged(self):
        self.showItems(aps = list(self.wificonfig.APs))
    #enddef


    def clientconnectButtonSubmit(self, data):
        return self.setclient(data['client-ssid'], data['client-psk'])
    #enddef


    def apsetButtonSubmit(self, data):
        return self.setap(data['ap-ssid'], data['ap-psk'])
    #enddef


    def wifioffButtonSubmit(self, data):
        try:
            self.wificonfig.DisableWifi()
        except:
            self.logger.error("Turning wifi off failed")
        #endtry
    #enddef


    def wifionButtonSubmit(self, data):
        try:
            self.wificonfig.EnableWifi()
        except:
            self.logger.error("Setting wifi on")
        #endtry
    #enddef


    def setclient(self, ssid, psk):
        pageWait = PageWait(self.display, line1 = _("Setting interface parameters"))
        pageWait.show()

        try:
            self.wificonfig.Connect(ssid, psk)
        except:
            self.logger.exception("Setting wifi client params failed: ssid:%s psk:%s", ssid, psk)
        #endtry

        # Connecting
        pageWait.showItems(line1 = _("Connecting"))
        try:
            for i in range(1, 10):
                sleep(1)
                if self.wificonfig.WifiConnectedSSID == ssid:
                    # Connection "ok"
                    return "_SELF_"
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
            self.wificonfig.StartHotspot(ssid, psk)
        except:
            self.logger.exception("Setting wifi AP params failed: ssid:%s psk:%s", ssid, psk)
        #endtry

        # Starting AP
        pageWait.showItems(line1 = _("Starting Access Point"))
        for i in range(1, 10):
            sleep(1)
            if self.wificonfig.WifiMode == "ap":
                # AP "ok"
                return "_SELF_"
            #endfor
        #endfor

        # Connection fail
        self.display.pages['error'].setParams(
                text = _("Starting AP failed!"))
        return "error"
    #enddef

#endclass
