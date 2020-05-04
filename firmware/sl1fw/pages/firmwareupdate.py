# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from glob import glob
from os import path
from time import sleep

import pydbus

from sl1fw import defines
from sl1fw.functions.system import shut_down
from sl1fw.pages import page
from sl1fw.pages.base import Page
from sl1fw.pages.wait import PageWait


@page
class PageFirmwareUpdate(Page):
    Name = "firmwareupdate"

    def __init__(self, display):
        super().__init__(display)
        self.pageUI = "firmwareupdate"
        self.old_items = None
        self.rauc = pydbus.SystemBus().get("de.pengutronix.rauc", "/")["de.pengutronix.rauc.Installer"]
        self.updateDataPeriod = 1

    def fillData(self):
        # Get list of available firmware files on USB
        fw_files = glob(path.join(defines.mediaRootPath, "**/*.raucb"))

        # Get Rauc flasher status and progress
        operation = None
        progress = None
        try:
            operation = self.rauc.Operation
            progress = self.rauc.Progress
        except Exception as e:
            self.logger.error("Rauc status read failed: %s", str(e))

        return {
            "firmwares": fw_files,
            "operation": operation,
            "progress": progress,
        }

    def show(self):
        self.items.update(self.fillData())
        super().show()
        self.showItems(**self.items)

    def updateData(self):
        items = self.fillData()
        if self.old_items != items:
            self.showItems(**items)
            self.old_items = items

    def flashButtonSubmit(self, data):
        try:
            fw_url = data["firmware"]
        except Exception as e:
            self.logger.error("Error reading data['firmware']: %s", str(e))
            self.display.pages["error"].setParams(text=_("Invalid firmware source!"))
            return "error"

        self.display.pages["yesno"].setParams(
            yesFce=self.fetchUpdate, yesParams={"fw_url": fw_url}, text=_("Do you really want to update the firmware?")
        )
        return "yesno"

    def fetchUpdate(self, fw_url):
        try:
            pageWait = PageWait(self.display, line1=_("Fetching firmware"))
            pageWait.show()
            self.display.inet.download_url(fw_url, defines.firmwareTempFile, page=pageWait)
        except Exception as e:
            self.logger.error("Firmware fetch failed: %s", str(e))
            self.display.pages["error"].setParams(text=_("Firmware fetch failed!"))
            return "error"

        return self.doUpdate(defines.firmwareTempFile)

    def doUpdate(self, fw_file):
        self.logger.info("Flashing: %s", fw_file)
        try:
            rauc = pydbus.SystemBus().get("de.pengutronix.rauc", "/")["de.pengutronix.rauc.Installer"]
            rauc.Install(fw_file)
        except Exception as e:
            self.logger.error("Rauc install call failed: %s", str(e))

        pageWait = PageWait(self.display, line1=_("Updating the firmware"))
        pageWait.show()

        try:
            while True:
                progress = self.rauc.Progress

                pageWait.showItems(line2=progress[1], line3="%d%%" % progress[0])

                # Check progress for update done
                if progress[1] == "Installing done.":
                    pageWait.showItems(line1=_("Update done"), line2=_("Shutting down"))
                    sleep(3)
                    shut_down(self.display.hw, True)

                # Check for operation failure
                if progress[1] == "Installing failed.":
                    raise Exception("Update failed")

                # Wait for a while
                sleep(1)

        except Exception as e:
            self.logger.error("Rauc update failed: %s", str(e))
            self.display.pages["error"].setParams(text=_("Update failed!"))
            return "error"
