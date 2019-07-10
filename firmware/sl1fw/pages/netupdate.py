# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import os
import shutil
import tempfile
import tarfile
import json
import paho.mqtt.publish as mqtt

from sl1fw import defines
from sl1fw.libPages import page, Page, PageWait


@page
class PageNetUpdate(Page):
    Name = "netupdate"

    def __init__(self, display):
        super(PageNetUpdate, self).__init__(display)
        self.pageUI = "admin"
        self.pageTitle = N_("Net Update")
        self.firmwares = []
    #enddef


    def show(self):
        # Create item for downloading examples
        self.items.update({
            "button14" : _("Send factory config"),
            "button15" : _("Download examples"),
        })

        try:
            query_url = defines.firmwareListURL + "/?serial=" + self.display.hw.cpuSerialNo + "&version=" + self.display.hwConfig.os.versionId
            self.downloadURL(query_url, defines.firmwareListTemp, title=_("Downloading firmware list"),
                             timeout_sec=5)

            with open(defines.firmwareListTemp) as list_file:
                self.firmwares = list(enumerate(json.load(list_file)))
            #endwith
        except:
            self.logger.exception("Failed to load firmware list from the net")
        #endtry

        # Create items for updating firmwares
        self.items.update({
            "button%s" % (i + 1): ("%s - %s") % (firmware['version'], firmware['branch']) for (i, firmware) in self.firmwares
        })

        # Create action handlers
        for (i, firmware) in self.firmwares:
            self.makeUpdateButton(i + 1, firmware['version'], firmware['url'])
        #endfor

        super(PageNetUpdate, self).show()
    #enddef


    def button14ButtonRelease(self):
        if self.display.wizardData.wizardResinVolume < 0:
            self.display.pages['error'].setParams(
                    backFce = self.gotoWizard,
                    text = _("The wizard was not finished successfully!"))
            return "error"
        #endif

        if not self.display.hwConfig.calibrated:
            self.display.pages['error'].setParams(
                    backFce = self.gotoCalib,
                    text = _("The calibration was not finished successfully!"))
            return "error"
        #endif

        if self.display.wizardData.uvFoundPwm < 0:
            self.display.pages['error'].setParams(
                    backFce = self.gotoUVcalib,
                    text = _("The automatic UV LED calibration was not finished successfully!"))
            return "error"
        #endif

        self.display.wizardData.update(
                osVersion = self.display.hwConfig.os.versionId,
                sl1fwVersion = defines.swVersion,
                a64SerialNo = self.display.hw.cpuSerialNo,
                mcSerialNo = self.display.hw.mcSerialNo,
                mcFwVersion = self.display.hw.mcFwVersion,
                mcBoardRev = self.display.hw.mcBoardRevision,
                towerHeight = self.display.hwConfig.towerHeight,
                tiltHeight = self.display.hwConfig.tiltHeight,
                uvPwm = self.display.hwConfig.uvPwm,
                )
        if not self.writeToFactory(self.display.wizardData.writeFile):
            self.display.pages['error'].setParams(
                text = _("!!! Failed to save factory defaults !!!"))
            return "error"
        #endif

        topic = "prusa/sl1/factoryConfig"
        data = self.display.wizardData.getJson()
        self.logger.debug("mqtt data: %s", data)
        try:
            mqtt.single(topic, data, qos=2, retain=True, hostname="mqttstage.prusa")
        except Exception as err:
            self.logger.error("mqtt message not delivered. %s", err)
            self.display.pages['error'].setParams(text = _("Cannot send factory config!"))
            return "error"
        #endtry

        self.display.pages['confirm'].setParams(
                continueFce = self.success,
                text = _("Factory config was successfully sent."))
        return "confirm"
    #enddef


    def gotoWizard(self):
        return "wizardinit"
    #enddef


    def gotoCalib(self):
        return "calibration1"
    #enddef


    def gotoUVcalib(self):
        return "uvcalibrationtest"
    #enddef


    def success(self):
        return "_BACK_"
    #enddef


    def button15ButtonRelease(self):
        try:
            if not os.path.isdir(defines.internalProjectPath):
                os.makedirs(defines.internalProjectPath)
            #endif

            # TODO: With python 3 we could:
            # with tempfile.TemporaryFile() as archive:
            archive = tempfile.mktemp(suffix=".tar.gz")

            self.downloadURL(defines.examplesURL, archive, title=_("Fetching examples"))

            pageWait = PageWait(self.display, line1=_("Decompressing examples"))
            pageWait.show()
            pageWait.showItems(line1=_("Extracting examples"))

            #TODO: With python 3 we could:
            #with tempfile.TemporaryDirectory() as temp:
            temp = tempfile.mkdtemp()
            with tarfile.open(archive) as tar:
                for member in tar.getmembers():
                    tar.extract(member, temp)
                #endfor
            #endwith
            pageWait.showItems(line1=_("Storing examples"))
            for item in os.listdir(temp):
                dest = os.path.join(defines.internalProjectPath, item)
                if os.path.exists(dest):
                    shutil.rmtree(dest)
                #endif
                shutil.copytree(os.path.join(temp, item), dest)
            #endfor

            pageWait.showItems(line1=_("Cleaning up"))
            #endwith

            return "_BACK_"
        #endtry

        except Exception as e:
            self.logger.error("Exaples fetch failed: " + str(e))
            self.display.pages['error'].setParams(
                text=_("Examples fetch failed"))
            return "error"
        #endexcept

        finally:
            try:
                if os.path.exists(archive):
                    os.remove(archive)
                #endif
                if os.path.exists(temp):
                    shutil.rmtree(temp)
                #endif
            except:
                self.logger.exception("Failed to remove examples debries")
            #endtry
        #endtry
    #enddef


    def makeUpdateButton(self, i, name, url):
        setattr(self.__class__, 'button%dButtonRelease' % i, lambda x: x.update(name, url))
    #enddef


    def update(self, name, url):
        self.display.pages['yesno'].setParams(
            yesFce = self.display.pages['firmwareupdate'].fetchUpdate,
            yesParams = { 'fw_url': url },
            text = _("Updating to %s.\n\nProceed update?") % name)
        return "yesno"
    #enddef

#endclass
