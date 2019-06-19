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
        wifisetup = pydbus.SystemBus().get('cz.prusa3d.sl1.wifisetup')

        aps = {}
        for ap in wifisetup.GetAPs():
            aps[ap['ssid']] = ap

        return {
            'devlist' : self.display.inet.getDevices(),
            'wifi_mode' : wifisetup.WifiMode,
            'client_ssid' : wifisetup.ClientSSID,
            'client_psk' : wifisetup.ClientPSK,
            'ap_ssid' : wifisetup.APSSID,
            'ap_psk' : wifisetup.APPSK,
            'aps' : list(aps.values()),
            'wifi_ssid' : wifisetup.WifiConnectedSSID,
            'wifi_signal' : wifisetup.WifiConnectedSignal,
        }
    #enddef


    def show(self):
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
            wifisetup = pydbus.SystemBus().get('cz.prusa3d.sl1.wifisetup')
            wifisetup.StartAP()
            wifisetup.EnableAP()
        except:
            self.logger.error("Setting wifi ap mode (wifi on)")
        #endtry
    #enddef


    def wifioff(self):
        try:
            wifisetup = pydbus.SystemBus().get('cz.prusa3d.sl1.wifisetup')
            wifisetup.StopWifi()
            wifisetup.DisableWifi()
        except:
            self.logger.error("Turning wifi off failed")
        #endtry
        return "_BACK_"
    #enddef


    def setclient(self, ssid, psk):
        pageWait = PageWait(self.display, line1 = _("Setting interface params..."))
        pageWait.show()

        try:
            wifisetup = pydbus.SystemBus().get('cz.prusa3d.sl1.wifisetup')
            wifisetup.ClientSSID = ssid
            wifisetup.ClientPSK = psk
            wifisetup.StartClient()
            wifisetup.EnableClient()
        except:
            self.logger.error("Setting wifi client params failed: ssid:%s psk:%s", ssid, psk)
        #endtry

        # Connecting...
        pageWait.showItems(line1 = _("Connecting..."))
        for i in range(1, 10):
            sleep(1)
            if 'wlan0' in self.display.inet.getDevices():
                # Connection "ok"
                return "_BACK_"
            #endfor
        #endfor

        # Connection fail
        self.display.pages['error'].setParams(
                text = _("Connection failed!"))
        return "error"
    #enddef


    def setap(self, ssid, psk):
        pageWait = PageWait(self.display, line1 = _("Setting interface params..."))
        pageWait.show()

        try:
            wifisetup = pydbus.SystemBus().get('cz.prusa3d.sl1.wifisetup')
            wifisetup.APSSID = ssid
            wifisetup.APPSK = psk
            wifisetup.StartAP()
            wifisetup.EnableAP()
        except:
            self.logger.error("Setting wifi AP params failed: ssid:%s psk:%s", ssid, psk)
        #endtry

        # Starting AP...
        pageWait.showItems(line1 = _("Starting AP..."))
        for i in range(1, 10):
            sleep(1)
            if 'ap0' in self.display.inet.getDevices():
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
