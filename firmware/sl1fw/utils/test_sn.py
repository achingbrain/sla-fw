#!/usr/bin/python2

# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import bitstring


if len(sys.argv) != 2:
    print("Usage: %s nvram_file" % sys.argv[0])
    exit(1)
#enddef

s = bitstring.BitArray(bytes=open(sys.argv[1], 'rb').read())

mac, mcs1, mcs2, snbe = s.unpack('pad:192, bits:48, uint:8, uint:8, pad:224, uintbe:64')

mcsc = mac.count(1)
if mcsc == mcs1 and mcsc ^ 255 == mcs2:
    print("MAC checksum OK (%02x:%02x)" % (mcs1, mcs2))
    print(":".join([x.encode("hex") for x in mac.bytes]))
else:
    print("MAC checksum FAIL (is %02x:%02x, should be %02x:%02x)" % (mcs1, mcs2, mcsc, mcsc ^ 255))
#endif


print()

# byte order change
sn = bitstring.BitArray(length = 64, uintle = snbe)

ot = { 0 : "CZP" }

scs2, scs1, snnew = sn.unpack('uint:8, uint:8, bits:48')

scsc = snnew.count(1)
if scsc == scs1 and scsc ^ 255 == scs2:
    print("SN checksum OK (%02x:%02x)" % (scs1, scs2))
    sequence_number, is_kit, ean_pn, year, week, origin = snnew.unpack('pad:4, uint:17, bool, uint:10, uint:6, uint:6, uint:4')
    txt = ""
else:
    print("SN checksum FAIL (is %02x:%02x, should be %02x:%02x)" % (scs1, scs2, scsc, scsc ^ 255))
    sequence_number, is_kit, ean_pn, year, week, origin = sn.unpack('pad:14, uint:17, bool, uint:10, uint:6, pad:2, uint:6, pad:2, uint:4')
    txt = "*"
#endif

print("%s%3sX%02u%02uX%03uX%c%05u" % (txt, ot.get(origin, "UNK"), week, year, ean_pn, "K" if is_kit else "C", sequence_number))
