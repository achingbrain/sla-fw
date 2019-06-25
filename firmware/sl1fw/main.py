#!/usr/bin/env python

# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import os
import logging
from systemd.journal import JournalHandler
import gettext

try:
    # Python2
    import __builtin__ as builtins
except:
    # Python 3
    import builtins as builtins
#endtry

import sl1fw
from sl1fw import libPrinter

handler = JournalHandler(SYSLOG_IDENTIFIER = 'SL1FW')
handler.setFormatter(logging.Formatter("%(levelname)s - %(name)s - %(message)s"))
logger = logging.getLogger('')
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

langs = dict()
localedir = os.path.join(os.path.dirname(sl1fw.__file__), "locales")
for lang in ('cs', 'de', 'fr', 'it', 'es', 'pl'):
    try:
        langs[lang] = gettext.translation('sl1fw', localedir=localedir, languages=[lang])
    except:
        logger.warning("Translation file for language %s not found.", lang)
    #endtry
#enddef

logger.info("Avaiable translations: %s", ", ".join(langs.keys()))

#langs['cs'].install()

# use system locale settings
gettext.install('sl1fw', localedir)
builtins.N_ = lambda x: x

printer = libPrinter.Printer()
printer.start()
