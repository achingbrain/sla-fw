# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import glob

from sl1fw import defines


def ramdiskCleanup(logger):
    project_files = []
    for ext in defines.projectExtensions:
        project_files.extend(glob.glob(defines.ramdiskPath + "/*" + ext))
    for project_file in project_files:
        logger.debug("removing '%s'", project_file)
        try:
            os.remove(project_file)
        except Exception as e:
            logger.exception("ramdiskCleanup() exception:")
