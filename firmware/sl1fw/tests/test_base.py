import logging
import sys
import tempfile
from pathlib import Path
from unittest import TestCase
from mock import Mock

from sl1fw.tests import samples
import sl1fw.tests.mocks.mcPortSim
import sl1fw.tests.mocks.pydbusSim
from sl1fw.tests.mocks.gettextSim import fake_gettext

fake_gettext()
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(name)s - %(message)s", level=logging.DEBUG)

sys.modules['pydbus'] = sl1fw.tests.mocks.pydbusSim
sys.modules['gpio'] = Mock()
sys.modules['sl1fw.libDebug'] = Mock()
sys.modules['serial'] = sl1fw.tests.mocks.mcPortSim


class Sl1fwTestCase(TestCase):
    SL1FW_DIR = Path(sl1fw.__file__).parent
    SAMPLES_DIR = Path(sl1fw.tests.samples.__file__).parent
    TEMP_DIR = Path(tempfile.gettempdir())
    EEPROM_FILE = str(Path.cwd() / "EEPROM.dat")
