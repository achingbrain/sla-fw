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

fake_gettext()

sys.modules['gpio'] = Mock()
sys.modules['sl1fw.libDebug'] = Mock()
sys.modules['serial'] = sl1fw.tests.mcPortSim
sys.modules['pydbus'] = sl1fw.tests.pydbusSim

from sl1fw import libPrinter
from sl1fw import defines


class TestLibHardware(unittest.TestCase):
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
        defines.templates = os.path.join(os.path.dirname(__file__), "../intranet/templates")
        defines.hwConfigFile = self.HARDWARE_FILE
        defines.fbFile = self.FB_DEV_FILE
        defines.doFBSet = False
        defines.truePoweroff = False
        defines.internalProjectPath = os.path.join(os.path.dirname(__file__), "samples")
        defines.ramdiskPath = tempfile.gettempdir()
        defines.octoprintAuthFile = os.path.join(os.path.dirname(__file__), "samples/slicer-upload-api.key")

        os.environ['SDL_AUDIODRIVER'] = "disk"
        os.environ['SDL_DISKAUDIOFILE'] = self.SDL_AUDIO_FILE

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
        self.waitPage("home")

    def printer_thread(self):
        self.printer.start()
        # cProfile.runctx('self.printer.start()', globals=globals(), locals=locals())

    def tearDown(self):
        # Turn off the system
        self.press("turnoff")
        self.waitPage("yesno")
        self.press("yes")

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
        print("Pressing button: %s" % identifier)
        self.display.add_event(self.display.page, identifier, pressed=True, data=data)
        self.display.add_event(self.display.page, identifier, pressed=False, data=data)

    def waitPage(self, page, timeout_sec=3):
        self.assertEqual(page, self.display.read_page(timeout_sec=timeout_sec))

    def switchPage(self, page):
        self.press(page)
        self.waitPage(page)

    def test_init(self):
        pass

    def test_control(self):
        self.switchPage("control")
        # TODO: Make this test work
        # self.press("top")
        # self.press("tankres")
        self.press("disablesteppers")

    def test_support(self):
        self.switchPage("settings")
        self.switchPage("support")

        for page in ["manual", "videos", "sysinfo", "about"]:
            self.switchPage(page)
            self.press("back")
            self.waitPage("support")

        self.press("back")
        self.waitPage("settings")

        self.press("back")
        self.waitPage("home")

    def test_advancedsettings(self):
        self.switchPage("settings")
        self.switchPage("advancedsettings")

        # Test moves
        for page in ["towermove", "tiltmove"]:
            self.switchPage(page)

            for action in ["upfast", "upslow", "downfast", "downslow"]:
                self.press(action)

            self.press("back")
            self.waitPage("advancedsettings")

        # Test time settings
        self.switchPage("timesettings")

        self.press("ntpdisable")
        self.press("ntpenable")

        self.switchPage("settime")
        # TODO: Try changin time
        self.press("back")
        self.waitPage("timesettings")

        self.switchPage("settimezone")
        # TODO: Try changing timezone
        self.press("back")
        self.waitPage("timesettings")

        self.switchPage("setdate")
        # TODO: Try changing date
        self.press("back")
        self.waitPage("timesettings")

        self.press("back")
        self.waitPage("advancedsettings")

        # Test language settings
        self.switchPage("setlanguage")
        # TODO: Implement and try changing language
        self.press("back")
        self.waitPage("advancedsettings")

        # Test hostname settings
        self.switchPage("sethostname")
        # Try changning hostname
        self.press("back")
        self.waitPage("advancedsettings")

        # Test login credentials settings
        self.press("setremoteaccess")
        self.waitPage("setlogincredentials")
        self.press("back")
        self.waitPage("advancedsettings")

        # TODO: Test wizard

        # TODO: Test changing settings

        # Test display test - passing
        # TODO: Display test requires cover to be closed
        # self.switchPage("displaytest")
        # self.press("yes")
        # self.waitPage("advancedsettings")
        #
        # # Test display test - failing
        # self.switchPage("displaytest")
        # self.press("no")
        # self.waitPage("error")
        # self.press("ok")
        # self.waitPage("advancedsettings")

        # Test firmware update
        self.press("firmwareupdate")
        self.waitPage("wait")
        self.waitPage("firmwareupdate")
        self.press("back")
        self.waitPage("advancedsettings")

        self.press("back")
        self.waitPage("settings")

        self.press("back")
        self.waitPage("home")

    def test_print_not_calibrated(self):
        # Try to print
        self.press("print")
        # Expect problem with not being calibrated
        self.waitPage("yesno")
        # Return to home
        self.press("no")
        self.waitPage("home")

    def test_print(self):
        # Fake calibration
        self.printer.hwConfig.calibrated = True

        self.press("print")
        self.waitPage("sourceselect")
        self.press("source", data={'choice': 'choice0'})
        self.waitPage("wait")
        self.waitPage("printpreview")
        self.press("cont")
        self.waitPage("wait")
        # Ambient temperature is over recommended value.
        self.waitPage("yesno")
        self.press("no")
        self.waitPage("printpreview")

        # TODO: Say yes - continue print testing

        # Return to home
        self.press("back")
        self.waitPage("sourceselect")
        self.press("back")
        self.waitPage("home")

    def test_wizard(self):
        # TODO: Test wizard
        pass

    def test_calibration(self):
        # TODO: Test calibration
        pass


if __name__ == '__main__':
    unittest.main()
