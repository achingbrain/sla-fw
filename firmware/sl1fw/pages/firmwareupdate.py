# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import distro
import pydbus
import json
from time import sleep
from glob import glob
from os import path

from sl1fw import defines
from sl1fw.pages import page
from sl1fw.libPages import Page, PageWait


@page
class PageFirmwareUpdate(Page):
    Name = "firmwareupdate"

    def __init__(self, display):
        super(PageFirmwareUpdate, self).__init__(display)
        self.pageUI = "firmwareupdate"
        self.pageTitle = N_("Firmware Update")
        self.old_items = None
        self.rauc = pydbus.SystemBus().get("de.pengutronix.rauc", "/")["de.pengutronix.rauc.Installer"]
        self.updateDataPeriod = 1
    #enddef


    def getNetFirmwares(self):
        try:
            pageWait = PageWait(self.display, line1=_("Downloading firmware list"))
            pageWait.show()
            query_url = defines.firmwareListURL + "/?serial=" + self.display.hw.cpuSerialNo + "&version=" + distro.version()
            self.display.inet.download_url(query_url,
                    defines.firmwareListTemp,
                    distro.version(),
                    self.display.hw.cpuSerialNo,
                    page=pageWait,
                    timeout_sec=3)
            with open(defines.firmwareListTemp) as list_file:
                return json.load(list_file)
            #endwith
        except:
            self.logger.exception("Failed to load firmware list from the net")
            return []
        #endtry
    #enddef


    def fillData(self):
        # Get list of available firmware files on USB
        fw_files = glob(path.join(defines.mediaRootPath, "**/*.raucb"))

        # Get list of avaible firmware files on net
        try:
            for fw in self.net_list:
                if fw['branch'] != "stable":
                    continue

                if fw['version'] == distro.version():
                    continue

                fw_files.append(fw['url'])
            #endfor
        except:
            self.logger.exception("Failed to process net firmware list")
        #endtry

        # Get Rauc flasher status and progress
        operation = None
        progress = None
        try:
            operation = self.rauc.Operation
            progress = self.rauc.Progress
        except Exception as e:
            self.logger.error("Rauc status read failed: " + str(e))
        #endtry

        return {
            'firmwares' : fw_files,
            'operation' : operation,
            'progress' : progress,
        }
    #enddef


    def show(self):
        self.net_list = self.getNetFirmwares()
        self.items.update(self.fillData())
        super(PageFirmwareUpdate, self).show()
    #enddef


    def updateData(self):
        items = self.fillData()
        if self.old_items != items:
            self.showItems(**items)
            self.old_items = items
        #endif
    #enddef


    def flashButtonSubmit(self, data):
        try:
            fw_url = data['firmware']
        except Exception as e:
            self.logger.error("Error reading data['firmware']: " + str(e))
        #endtry

        self.display.pages['yesno'].setParams(
            yesFce = self.fetchUpdate,
            yesParams = { 'fw_url': fw_url },
            text = _("Do you really want to update the firmware?"))
        return "yesno"
    #enddef


    def fetchUpdate(self, fw_url):
        try:
            pageWait = PageWait(self.display, line1=_("Fetching firmware"))
            pageWait.show()
            self.display.inet.download_url(fw_url,
                    defines.firmwareTempFile,
                    distro.version(),
                    self.display.hw.cpuSerialNo,
                    page=pageWait)
        #endtry
        except Exception as e:
            self.logger.error("Firmware fetch failed: " + str(e))
            self.display.pages['error'].setParams(
                    text = _("Firmware fetch failed!"))
            return "error"
        #endexcept

        return self.doUpdate(defines.firmwareTempFile)
    #enddef


    def doUpdate(self, fw_file):
        self.logger.info("Flashing: " + fw_file)
        try:
            rauc = pydbus.SystemBus().get("de.pengutronix.rauc", "/")["de.pengutronix.rauc.Installer"]
            rauc.Install(fw_file)
        except Exception as e:
            self.logger.error("Rauc install call failed: " + str(e))
        #endtry

        pageWait = PageWait(self.display, line1 = _("Updating the firmware"))
        pageWait.show()

        try:
            while True:
                operation = self.rauc.Operation
                progress = self.rauc.Progress

                pageWait.showItems(
                    line2 = progress[1],
                    line3 = "%d%%" % progress[0]
                )

                # Check progress for update done
                if progress[1] == 'Installing done.':
                    pageWait.showItems(
                        line1 = _("Update done"),
                        line2 = _("Shutting down"))
                    sleep(3)
                    self.display.shutDown(True, reboot=True)
                #endif

                # Check for operation failure
                if progress[1] == 'Installing failed.':
                    raise Exception("Update failed")
                #endif

                # Wait for a while
                sleep(1)
            #endwhile
        #endtry

        except Exception as e:
            self.logger.error("Rauc update failed: " + str(e))
            self.display.pages['error'].setParams(
                    text = _("Update failed!"))
            return "error"
        #endexcept
    #enddef

#endclass
