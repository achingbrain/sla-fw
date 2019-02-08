#!/usr/bin/env python2

# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import logging
from systemd.journal import JournalHandler

from sl1fw import libPrinter

handler = JournalHandler(SYSLOG_IDENTIFIER = 'SL1FW')
handler.setFormatter(logging.Formatter("%(levelname)s - %(name)s - %(message)s"))
logger = logging.getLogger('')
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

printer = libPrinter.Printer()
printer.start()
