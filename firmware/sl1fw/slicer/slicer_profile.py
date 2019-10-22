# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import pprint

class SlicerProfile(dict):

    def __str__(self) -> str:
        pp = pprint.PrettyPrinter(width=200)
        return pp.pformat(self)

    @property
    def vendor(self) -> dict:
        return self['vendor']

    @property
    def printer(self) -> dict:
        return self['printer']
