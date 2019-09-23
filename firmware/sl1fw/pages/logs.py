# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import json

from sl1fw import defines
from sl1fw.pages import page
from sl1fw.libPages import Page


@page
class PageLogging(Page):
    Name = "logging"

    def __init__(self, display):
        super(PageLogging, self).__init__(display)
        self.pageUI = "setup"
        self.pageTitle = N_("Logging")
        self.debugEnabled = False
        self.loggingData = None
    #enddef


    def show(self):
        try:
            with open(defines.loggingConfig, "r") as f:
                self.loggingData = json.load(f)
            #endwith
            self.debugEnabled = self.loggingData['root']['level'] == "DEBUG"
        except:
            self.logger.exception("Failed to load json file")
            self.loggingData = None
        #endtry

        self.items.update({
            'label1g1' : _("Debug"),
            'state1g1' : int(self.debugEnabled),
            'button1' : _("Export to USB"),
            'button4' : _("Save settings"),
        })
        super(PageLogging, self).show()
    #enddef


    def state1g1ButtonRelease(self):
        self.debugEnabled = not self.debugEnabled
    #enddef


    def button1ButtonRelease(self):
        return self.saveLogsToUSB()
    #enddef


    def button4ButtonRelease(self):
        if not self.loggingData:
            self.display.pages['error'].setParams(text = _("Definitions are not loaded"))
            return "error"
        #endif
        self.loggingData['root']['level'] = "DEBUG" if self.debugEnabled else "INFO"
        try:
            with open(defines.loggingConfig, "w") as f:
                json.dump(self.loggingData, f, indent=4)
            #endwith
        except:
            self.logger.exception("Failed to save json file")
            self.display.pages['error'].setParams(text = _("Failed to save definitions file"))
            return "error"
        #endtry

        # force all forked processes to reload logging settings is overkill, let user do it
        self.display.pages['confirm'].setParams(
                text = _("The setting become active after the printer's restart."))
        return "confirm"
    #enddef

#endclass
