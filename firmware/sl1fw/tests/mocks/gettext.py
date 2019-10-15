# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import builtins as builtins


def _identity(message):
    return message


def fake_gettext():
    builtins._ = _identity
    builtins.N_ = _identity





