# This file is part of the SL1 firmware
# Copyright (C) 2020 Prusa Research a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

def toBase32hex(number:int) -> str:
    """Encode a integer in Base32hex without padding"""
    encode = "0123456789ABCDEFGHIJKLMNOPQRSTUV"
    buff = []
    while number > 32:
        buff.insert(0, encode[number % 32])
        number = number // 32

    buff.insert(0, encode[number])
    return "".join(buff)
