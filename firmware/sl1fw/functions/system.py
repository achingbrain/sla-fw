# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import os

from sl1fw import defines, libConfig
from sl1fw.libHardware import Hardware


def shut_down(hw: Hardware, reboot=False):
    if defines.testing:
        print("Skipping poweroff due to testing")
        return

    hw.uvLed(False)
    hw.motorsRelease()

    if reboot:
        os.system("reboot")
    else:
        os.system("poweroff")


def save_factory_mode(enable: bool):
    """
    Save factory mode

    This has to be called with factory partition mounted rw

    :param enable: Required factory mode state
    :return: True if successful, false otherwise
    """
    return libConfig.TomlConfig(defines.factoryConfigFile).save(data={"factoryMode": enable})
