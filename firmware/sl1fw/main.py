#!/usr/bin/env python2

# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018 Prusa Research s.r.o. - www.prusa3d.com

import logging
from sl1fw import libPrinter
from sl1fw import defines

logging.basicConfig(
        filename = defines.printerlog,
        #filemode = "w",
        level = logging.DEBUG,
        format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s")

printer = libPrinter.Printer()
printer.start()
