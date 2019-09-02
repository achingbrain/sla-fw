import logging
import unittest
from mock import Mock
import sys
import os
import threading
from shutil import copyfile
import tempfile
# import cProfile

from sl1fw.tests.gettextSim import fake_gettext
from sl1fw.tests.testdisplay import TestDisplay
import sl1fw.tests.mcPortSim
import sl1fw.tests.pydbusSim
import sl1fw.tests.libNetworkSim

fake_gettext()

sys.modules['gpio'] = Mock()
sys.modules['sl1fw.libDebug'] = Mock()
sys.modules['serial'] = sl1fw.tests.mcPortSim
sys.modules['pydbus'] = sl1fw.tests.pydbusSim
sys.modules['sl1fw.libNetwork'] = sl1fw.tests.libNetworkSim

from sl1fw import libPrinter
from sl1fw import defines
from sl1fw.pages.printstart import PagePrintPreview

logging.basicConfig(format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s", level = logging.DEBUG)


class TestIntegrationBase(unittest.TestCase):
    EEPROM_FILE = "EEPROM.dat"
    FB_DEV_FILE = "FBDEV.dat"
    HARDWARE_FILE = "hardware.cfg"
    SDL_AUDIO_FILE = os.path.join(tempfile.gettempdir(), "sl1fw.sdlaudio.raw")

    def setUp(self):
        copyfile(os.path.join(os.path.dirname(__file__), "samples/hardware.cfg"), self.HARDWARE_FILE)

        defines.cpuSNFile = os.path.join(os.path.dirname(__file__), "samples/nvmem")
        defines.cpuTempFile = os.path.join(os.path.dirname(__file__), "samples/cputemp")
        defines.factoryConfigFile = os.path.join(os.path.dirname(__file__), "../../factory/factory.toml")
        defines.hwConfigFactoryDefaultsFile = os.path.join(os.path.dirname(__file__), "samples/hardware.toml")
        defines.lastProjectData = os.path.join(os.path.dirname(__file__), "samples/lastProject.toml")
        defines.templates = os.path.join(os.path.dirname(__file__), "../intranet/templates")
        defines.multimediaRootPath = os.path.join(os.path.dirname(__file__), "../multimedia")
        defines.hwConfigFile = self.HARDWARE_FILE
        defines.fbFile = self.FB_DEV_FILE
        defines.doFBSet = False
        defines.truePoweroff = False
        defines.internalProjectPath = os.path.join(os.path.dirname(__file__), "samples")
        defines.ramdiskPath = tempfile.gettempdir()
        defines.octoprintAuthFile = os.path.join(os.path.dirname(__file__), "samples/slicer-upload-api.key")
        defines.livePreviewImage = os.path.join(defines.ramdiskPath, "live.png")

        os.environ['SDL_AUDIODRIVER'] = "disk"
        os.environ['SDL_DISKAUDIOFILE'] = self.SDL_AUDIO_FILE

        PagePrintPreview.FanCheckOverride = True

        self.display = TestDisplay()
        self.printer = libPrinter.Printer(debugDisplay=self.display)

        self.thread = threading.Thread(target=self.printer_thread)
        self.thread.start()

        # Skip failed to load factory defaults
        self.waitPage("error")
        self.press("ok")

        # Skip wizard
        self.waitPage("confirm")
        self.press("back")
        self.waitPage("yesno")
        self.press("yes")
        if os.path.isfile(defines.lastProjectData):
            self.waitPage("finished")
            self.press("home")
        self.waitPage("home")

    def printer_thread(self):
        self.printer.start()
        # cProfile.runctx('self.printer.start()', globals=globals(), locals=locals())

    def tearDown(self):
        self.printer.exit()
        self.thread.join()

        files = [
            self.EEPROM_FILE,
            self.FB_DEV_FILE,
            self.HARDWARE_FILE,
            self.SDL_AUDIO_FILE]

        for file in files:
            if os.path.isfile(file):
                os.remove(file)

    def press(self, identifier, data=None):
        print("Pressing button: %s on page %s" % (identifier, self.display.page))
        self.display.add_event(self.display.page, identifier, pressed=True, data=data)
        self.display.add_event(self.display.page, identifier, pressed=False, data=data)

    def waitPage(self, page, timeout_sec=3):
        self.assertEqual(page, self.display.read_page(timeout_sec=timeout_sec))
        print("Wait done for: %s" % page)

    def switchPage(self, page):
        self.press(page)
        self.waitPage(page)

