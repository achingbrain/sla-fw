# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import pkgutil
from importlib import import_module
from os import path

# List all page modules and import them
__all__ = [module for (_, module, _) in pkgutil.iter_modules([path.dirname(__file__)])]

for module in __all__:
    import_module(f"{__package__}.{module}")
