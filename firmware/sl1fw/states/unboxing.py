# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from enum import Enum, unique


@unique
class UnboxingState(Enum):
    INIT = 0  # Before start
    STICKER = 1  # Remove safety sticker, open the cover
    COVER_CLOSED = 2  # Wait for cover open
    MOVING_TO_FOAM = 3  # Printer moving for easier manipulation
    SIDE_FOAM = 4  # Remove black fom on the side of the printer
    MOVING_TO_TANK = 5  # Printer moving for easier manipulation
    TANK_FOAM = 6  # Remove resin tank
    DISPLAY_FOIL = 7  # Peel off exposure display foil
    FINISHED = 8
    CANCELED = 9
