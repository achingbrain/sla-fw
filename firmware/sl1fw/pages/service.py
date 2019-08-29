# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import os
import numpy
from PIL import Image

from sl1fw import defines
from sl1fw.pages import page
from sl1fw.libPages import Page
from sl1fw.libConfig import TomlConfigStats

@page
class PageService(Page):
    Name = "service"

    def __init__(self, display):
        super(PageService, self).__init__(display)
        self.pageUI = "admin"
        self.pageTitle = N_("Service")
    #enddef


    def show(self):
        stats = TomlConfigStats(defines.statsData, self.display.hw).load()
        minutes = stats['total_seconds'] // 60
        self.items.update({
                'button1' : _("TODO"),

                'button6' : _("Projects: %d") % stats['projects'],
                'button7' : _("Layers: %d") % stats['layers'],
                'button8' : _("Total time: %dh%02dm") % (minutes // 60, minutes % 60),
                'button9' : _("Display usage heatmap"),

                })
        super(PageService, self).show()
    #enddef


    def button9ButtonRelease(self):
        return "displayusage"
    #enddef

#endclass


@page
class PageDisplayUsage(Page):
    Name = "displayusage"

    def __init__(self, display):
        super(PageDisplayUsage, self).__init__(display)
        self.pageUI = "picture"
        self.pageTitle = N_("Display usage heatmap")
        self.palette = None
        try:
            paletteBytes = bytes()
            with open(defines.displayUsagePalette, "r") as f:
                for line in f:
                    paletteBytes += bytes.fromhex(line.strip()[1:])
                #endfor
            #endwith
            self.palette = list(paletteBytes)
        except:
            self.logger.exception("load palette failed")
        #endtry
    #enddef


    def prepare(self):
        try:
            with numpy.load(defines.displayUsageData) as npzfile:
                savedData = npzfile['display_usage']
            #endwith
        except:
            self.logger.exception("load display usage failed")
            savedData = None
        #endtry

        if savedData is None:
            self.display.pages['error'].setParams(text = _("No data to show!"))
            return "error"
        #endif

        imagePath = os.path.join(defines.ramdiskPath, "displayhm.png")
        self.generateDisplayUsageHeatmap(imagePath, savedData)
        self.setItems(image_path = "file://%s" % imagePath)
    #enddef


    def generateDisplayUsageHeatmap(self, filename, data):
        maxValue = data.max()
        # 0-255 range
        data = data * 255 / maxValue
        image = Image.fromarray(data.astype('int8'), 'P')
        if self.palette:
            image.putpalette(self.palette)
        #endif
        image.save(filename)
    #enddef


    def _EXIT_(self):
        return "_EXIT_"
    #enddef


    def _BACK_(self):
        return "_BACK_"
    #enddef

#endclass