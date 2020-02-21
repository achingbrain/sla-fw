# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.states.display import DisplayState
from sl1fw.pages import page
from sl1fw.pages.base import Page


@page
class PageAdmin(Page):
    Name = "admin"

    def __init__(self, display):
        super(PageAdmin, self).__init__(display)
        self.pageUI = "admin"
    #enddef


    def show(self):
        self.display.state = DisplayState.ADMIN
        self.items.update({
                'button1' : "Tilt & Tower",
                'button2' : "Display",
                'button3' : "Fans & UV LED",
                'button4' : "Hardware setup",
                'button5' : "Exposure setup",

                'button6' : "Motion Controller",
                'button7' : "Tests",
                'button8' : "Service",
                'button9' : "Wizards",

                'button11' : "Net update",
                'button12' : "Logging",
                'button13' : "System Information",
                })
        super(PageAdmin, self).show()
    #enddef


    @staticmethod
    def button1ButtonRelease():
        return "tilttower"
    #enddef


    @staticmethod
    def button2ButtonRelease():
        return "display"
    #enddef


    @staticmethod
    def button3ButtonRelease():
        return "fansleds"
    #enddef


    @staticmethod
    def button4ButtonRelease():
        return "setuphw"
    #enddef


    @staticmethod
    def button5ButtonRelease():
        return "setupexpo"
    #enddef


    @staticmethod
    def button6ButtonRelease():
        return "motioncontroller"
    #enddef


    @staticmethod
    def button7ButtonRelease():
        return "tests"
    #enddef


    @staticmethod
    def button8ButtonRelease():
        return "service"
    #enddef


    @staticmethod
    def button9ButtonRelease():
        return "testwizards"
    #enddef


    @staticmethod
    def button11ButtonRelease():
        return "netupdate"
    #enddef


    @staticmethod
    def button12ButtonRelease():
        return "logging"
    #enddef


    @staticmethod
    def button13ButtonRelease():
        return "sysinfo"
    #enddef

#endclass
