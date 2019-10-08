#!/usr/bin/env python

# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import logging
import gettext
import builtins

from sl1fw import defines
from sl1fw.logger_config import configure_log

log_from_config = configure_log()
logger = logging.getLogger()

if log_from_config:
    logger.info("Logging configuration read from configuration file")
else:
    logger.info("Embedded logger configuration was used")
#endif

logger.info("Logging set to level %s", logging.getLevelName(logger.level))


langs = dict()

for lang in ('cs', 'de', 'fr', 'it', 'es', 'pl'):
    try:
        langs[lang] = gettext.translation('sl1fw', localedir=defines.localedir, languages=[lang])
    except:
        logger.warning("Translation file for language %s not found.", lang)
    #endtry
#enddef

logger.info("Avaiable translations: %s", ", ".join(langs.keys()))

# use system locale settings
gettext.install('sl1fw', defines.localedir)
builtins.N_ = lambda x: x

from sl1fw import libPrinter

printer = libPrinter.Printer()
printer.run()
