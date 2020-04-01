# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
from time import time

import pydbus

from sl1fw.pages import page
from sl1fw.pages.base import Page


class PageTimeDateBase(Page):

    def __init__(self, display):
        self._timedate = None
        super(PageTimeDateBase, self).__init__(display)
    #enddef


    @property
    def timedate(self):
        if not self._timedate:
            self._timedate = pydbus.SystemBus().get("org.freedesktop.timedate1")
        #endif
        return self._timedate
    #enddef

#endclass


@page
class PageTimeSettings(PageTimeDateBase):
    Name = "timesettings"

    def __init__(self, display):
        super(PageTimeSettings, self).__init__(display)
        self.pageUI = "timesettings"
    #enddef


    def fillData(self):
        return {
            'ntp' : self.timedate.NTP,
            'unix_timestamp_sec' : time(),
            'timezone' : self.timedate.Timezone,
        }
    #enddef


    def show(self):
        self.items.update(self.fillData())
        super(PageTimeSettings, self).show()
    #enddef


    def ntpenableButtonRelease(self):
        self.timedate.SetNTP(True, False)
    #enddef


    def ntpdisableButtonRelease(self):
        self.timedate.SetNTP(False, False)
    #enddef

    @staticmethod
    def settimeButtonSubmit(_data):
        return "settime"
    #enddef

    @staticmethod
    def setdateButtonSubmit(_data):
        return "setdate"
    #enddef

    @staticmethod
    def settimezoneButtonSubmit(_data):
        return "settimezone"
    #enddef

#endclass


class PageSetTimeBase(PageTimeDateBase):

    def fillData(self):
        return {
            'unix_timestamp_sec' : time(),
            'timezone' : self.timedate.Timezone,
        }
    #enddef


    def show(self):
        self.items.update(self.fillData())
        super(PageSetTimeBase, self).show()
    #enddef


    def settimeButtonSubmit(self, data):
        self.timedate.SetTime(float(data['unix_timestamp_sec']) * 1000000, False, False)
        return "_BACK_"
    #enddef

#endclass


@page
class PageSetTime(PageSetTimeBase):
    Name = "settime"

    def __init__(self, display):
        super(PageSetTime, self).__init__(display)
        self.pageUI = "settime"
    #enddef

#endclass


@page
class PageSetDate(PageSetTimeBase):
    Name = "setdate"

    def __init__(self, display):
        super(PageSetDate, self).__init__(display)
        self.pageUI = "setdate"
    #enddef

#endclass


@page
class PageSetTimezone(PageTimeDateBase):
    Name = "settimezone"
    zone_info = Path("/usr/share/zoneinfo")

    def __init__(self, display):
        super(PageSetTimezone, self).__init__(display)
        self.pageUI = "settimezone"

        # Available timezones
        regions = self.zone_info.glob("*")
        self.timezones = {region.name: [city.name for city in region.glob("*") if city.is_file()] for region in regions}
    #enddef


    def fillData(self):
        try:
            timezone = self.timedate.Timezone
            region, city = timezone.split('/')
        except:
            timezone = "UTC"
            region = "Etc"
            city = "GTM"

        return {
            'timezone' : timezone,
            'region' : region,
            'city' : city,
            'timezones' : self.timezones,
        }
    #enddef


    def show(self):
        self.items.update(self.fillData())
        super(PageSetTimezone, self).show()
    #enddef


    def settimezoneButtonSubmit(self, data):
        try:
            timezone = "%s/%s" % (data['region'], data['city'])
        except:
            timezone = data['timezone']

        self.timedate.SetTimezone(timezone, False)

        return "_BACK_"
    #enddef

#endclass
