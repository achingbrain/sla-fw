# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.pages import page
from sl1fw.libPages import Page


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

                'button6' : _("Motion Controller"),
                'button7' : _("Tests"),
                'button8' : _("Service"),

                'button11' : _("Net update"),
                'button12' : _("Logging"),
                'button13' : _("System Information"),
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
        return "motioncontroller"
    #enddef


    def button7ButtonRelease(self):
        return "tests"
    #enddef


    def button8ButtonRelease(self):
        return "service"
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

#endclass
