# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import os
import shutil
import tempfile
import tarfile
import json
import distro
import paho.mqtt.publish as mqtt

from sl1fw import defines
from sl1fw.pages import page
from sl1fw.libPages import Page, PageWait


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
            pageWait = PageWait(self.display, line1=_("Downloading firmware list"))
            pageWait.show()
            query_url = defines.firmwareListURL + "/?serial=" + self.display.hw.cpuSerialNo + "&version=" + distro.version()
            self.display.inet.download_url(query_url,
                    defines.firmwareListTemp,
                    distro.version(),
                    self.display.hw.cpuSerialNo,
                    page=pageWait,
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
        if not self.display.hw.isKit:
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
        #enddef

        if self.display.wizardData.uvFoundPwm < 1:
            self.display.pages['error'].setParams(
                    backFce = self.gotoUVcalib,
                    text = _("The automatic UV LED calibration was not finished successfully!"))
            return "error"
        #endif

        writer = self.display.wizardData.get_writer()
        writer.osVersion = distro.version()
        writer.a64SerialNo = self.display.hw.cpuSerialNo
        writer.mcSerialNo = self.display.hw.mcSerialNo
        writer.mcFwVersion = self.display.hw.mcFwVersion
        writer.mcBoardRev = self.display.hw.mcBoardRevision
        writer.towerHeight = self.display.hwConfig.towerHeight
        writer.tiltHeight = self.display.hwConfig.tiltHeight
        writer.uvPwm = self.display.hwConfig.uvPwm

        if not self.writeToFactory(writer.commit):
            self.display.pages['error'].setParams(
                text = _("!!! Failed to save factory defaults !!!"))
            return "error"
        #endif

        topic = "prusa/sl1/factoryConfig"
        data = json.dumps(self.display.wizardData.as_dictionary(nondefault=True))
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

            with tempfile.NamedTemporaryFile() as archive:
                pageWait = PageWait(self.display, line1=_("Fetching examples"))
                pageWait.show()
                self.display.inet.download_url(defines.examplesURL,
                        archive.name,
                        distro.version(),
                        self.display.hw.cpuSerialNo,
                        page=pageWait)

                pageWait.showItems(line1=_("Extracting examples"), line2="")

                with tempfile.TemporaryDirectory() as temp:
                    with tarfile.open(fileobj=archive) as tar:
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
            #endwith

            return "_BACK_"
        #endtry

        except Exception as e:
            self.logger.exception("Exaples fetch failed: " + str(e))
            self.display.pages['error'].setParams(
                text=_("Examples fetch failed"))
            return "error"
        #endexcept
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
