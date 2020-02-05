# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import glob
from logging import Logger
from PIL import Image
import numpy

from sl1fw import defines


def ramdisk_cleanup(logger: Logger) -> None:
    project_files = []
    for ext in defines.projectExtensions:
        project_files.extend(glob.glob(defines.ramdiskPath + "/*" + ext))
    for project_file in project_files:
        logger.debug("removing '%s'", project_file)
        try:
            os.remove(project_file)
        except Exception:
            logger.exception("ramdisk_cleanup() exception:")

def get_white_pixels(image: Image) -> int:
    np_array = numpy.array(image.histogram())
    return int(numpy.sum(np_array[128:]))   # simple treshold
