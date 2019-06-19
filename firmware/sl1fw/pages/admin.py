# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import os
import subprocess
import signal

from sl1fw import defines
from sl1fw.libPages import page, Page, PageWait


@page
class PageAdmin(Page):
    Name = "admin"

    def __init__(self, display):
        super(PageAdmin, self).__init__(display)
        self.pageUI = "admin"
        self.pageTitle = N_("Admin Home")
    #enddef


    def show(self):
        self.items.update({
                'button1' : _("Tilt & Tower"),
                'button2' : _("Display"),
                'button3' : _("Fans & UV LED"),
                'button4' : _("Hardware setup"),
                'button5' : _("Exposure setup"),

                'button6' : _("Flash MC"),
                'button7' : _("Erase MC EEPROM"),
                'button8' : _("MC2Net (bootloader)"),
                'button9' : _("MC2Net (firmware)"),
                'button10' : _("Resin sensor test"),

                'button11' : _("Net update"),
                'button12' : _("Logging"),
                'button13' : _("System Information"),
                'button14' : "",
                'button15' : _("Raise exception"),
                })
        super(PageAdmin, self).show()
    #enddef


    def button1ButtonRelease(self):
        return "tilttower"
    #enddef


    def button2ButtonRelease(self):
        return "display"
    #enddef


    def button3ButtonRelease(self):
        return "fansleds"
    #enddef


    def button4ButtonRelease(self):
        return "setuphw"
    #enddef


    def button5ButtonRelease(self):
        return "setupexpo"
    #enddef


    def button6ButtonRelease(self):
        self.display.pages['yesno'].setParams(
                yesFce = self.button6Continue,
                text = _("This overwrites the motion controller with the selected firmware."))
        return "yesno"
    #enddef


    def button6Continue(self):
        pageWait = PageWait(self.display)
        self.display.hw.flashMC(pageWait, self.display.actualPage)
        return "_BACK_"
    #enddef


    def button7ButtonRelease(self):
        self.display.pages['yesno'].setParams(
                yesFce = self.button7Continue,
                text = _("This will erase all profiles and other motion controller settings."))
        return "yesno"
    #enddef


    def button7Continue(self):
        pageWait = PageWait(self.display, line1 = _("Erasing EEPROM"))
        pageWait.show()
        self.display.hw.eraseEeprom()
        self.display.hw.initDefaults()
        return "_BACK_"
    #enddef


    def button8ButtonRelease(self):
        self.display.pages['yesno'].setParams(
                yesFce = self.mc2net,
                yesParams = { 'bootloader' : True },
                text = _("This will disable the GUI and connect the MC bootloader to TCP port."))
        return "yesno"
    #enddef


    def button9ButtonRelease(self):
        self.display.pages['yesno'].setParams(
                yesFce = self.mc2net,
                yesParams = { 'bootloader' : False },
                text = _("This will disable the GUI and connect the motion controller to TCP port."))
        return "yesno"
    #enddef


    def mc2net(self, bootloader = False):
        ip = self.display.inet.getIp()
        if ip == "none":
            self.display.pages['error'].setParams(
                    text = _("Not connected to network"))
            return "error"
        #endif

        baudrate = 19200 if bootloader else 115200
        if bootloader:
            self.display.hw.mcc.reset()
        #endif

        self.display.hw.switchToDummy()

        pid = subprocess.Popen([
            defines.Mc2NetCommand,
            defines.motionControlDevice,
            str(defines.socatPort),
            str(baudrate)], preexec_fn=os.setsid).pid

        self.display.pages['confirm'].setParams(
                continueFce = self.mc2netStop,
                continueParams = { 'pid' : pid },
                backFce = self.mc2netStop,
                backParams = { 'pid' : pid },
                text = _("Baudrate is %(br)d.\n\n"
                    "Serial line is redirected to %(ip)s:%(port)d.\n\n"
                    "Press 'Continue' when done.") % { 'br' : baudrate, 'ip' : ip, 'port' : defines.socatPort })
        return "confirm"
    #enddef


    def mc2netStop(self, pid):
        os.killpg(os.getpgid(pid), signal.SIGTERM)
        pageWait = PageWait(self.display)
        self.display.hw.switchToMC(pageWait, self.display.actualPage)
        return "_BACK_"
    #enddef


    def button10ButtonRelease(self):
        self.display.pages['yesno'].setParams(
                yesFce = self.button10Continue,
                text = _("Is there the correct amount of resin in the tank?\n\n"
                    "Is the tank secured with both screws?"))
        return "yesno"
    #enddef


    def button10Continue(self):
        # TODO vyzadovat zavreny kryt po celou dobu!
        self.display.hw.powerLed("warn")
        pageWait = PageWait(self.display, line1 = _("Moving platform to the top"))
        pageWait.show()
        retc = self._syncTower(pageWait)
        if retc == "error":
            return retc
        #endif
        pageWait.showItems(line1 = _("Tilt home"), line2 = "")
        pageWait.show()
        retc = self._syncTilt()
        if retc == "error":
            return retc
        #endif
        self.display.hw.setTiltProfile('layerMoveSlow')
        self.display.hw.tiltUpWait()

        pageWait.showItems(line2 = _("Measuring..."), line3 = _("Do NOT TOUCH the printer"))
        volume = self.display.hw.getResinVolume()
        self.display.hw.powerLed("normal")
        if not volume:
            self.display.pages['error'].setParams(
                    text = _("Resin measuring failed!\n\n"
                        "Is there the correct amount of resin in the tank?\n\n"
                        "Is the tank secured with both screws?"))
            return "error"
        #endif

        self.display.pages['confirm'].setParams(
                continueFce = self.backButtonRelease,
                text = _("Measured resin volume: %d ml") % volume)
        return "confirm"
    #enddef


    def button11ButtonRelease(self):
        return "netupdate"
    #enddef


    def button12ButtonRelease(self):
        return "logging"
    #enddef


    def button13ButtonRelease(self):
        return "sysinfo"
    #enddef


    def button14ButtonRelease(self):
        pass
    #enddef


    def button15ButtonRelease(self):
        raise Exception("Test problem")
    #enddef

#endclass
