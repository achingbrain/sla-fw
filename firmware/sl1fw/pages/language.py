# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import pydbus

from sl1fw.libConfig import ConfigException
from sl1fw.pages import page
from sl1fw.pages.base import Page


@page
class PageSetLanguage(Page):
    Name = "setlanguage"

    def __init__(self, display):
        super(PageSetLanguage, self).__init__(display)
        self.pageUI = "setlanguage"
        self._locale = None
    #enddef


    @property
    def locale(self):
        if not self._locale:
            self._locale = pydbus.SystemBus().get("org.freedesktop.locale1")
        #endif
        return self._locale
    #enddef


    def fillData(self):
        try:
            locale = str(self.locale.Locale)
            lang = re.match(".*'LANG=(.*)'.*", locale).groups()[0]
        except:
            lang = ""

        return {
            'locale' : lang,
        }
    #enddef


    def show(self):
        self.items.update(self.fillData())
        super(PageSetLanguage, self).show()
    #enddef


    def setlocaleButtonSubmit(self, data):
        try:
            self.locale.SetLocale([data['locale']], False)
        except:
            self.logger.exception("Setting locale failed")
        #endtry

        self.display.hwConfig.showI18nSelect = False
        try:
            self.display.hwConfig.write()
        except ConfigException:
            self.logger.exception("Failed to save language configuration")
            self.display.pages['error'].setParams(
                text = _("Cannot save language configuration"))
            return "error"
        #endif

        return "_BACK_"
    #enddef

#endclass
