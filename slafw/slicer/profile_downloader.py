# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# TODO: Fix following pylint problems
# pylint: disable=no-else-return

import logging
from pathlib import Path

from slafw import defines


class ProfileDownloader:

    INDEX_FILENAME = "index.idx"
    VERSION_SUFFIX = ".ini"

    def __init__(self, inet, vendor):
        self.logger = logging.getLogger(__name__)
        self.inet = inet
        self.vendor = vendor


    def checkUpdates(self) -> str:
        updateURL = self.vendor.get('config_update_url', None)
        if not updateURL:
            self.logger.error("Missing 'config_update_url' key")
            return ""
        try:
            updateURL += self.INDEX_FILENAME
            tmpfile = Path(defines.ramdiskPath) / self.INDEX_FILENAME
            self.inet.download_url(updateURL, tmpfile)
            slicerMinVersion = None
            version, note  = None, None
            with open(tmpfile, "r") as f:
                while True:
                    line = f.readline().strip()
                    if not line:
                        break
                    if line.startswith("min_slic3r_version"):
                        slicerMinVersion = line.split("=")[1].strip()
                    elif slicerMinVersion != defines.slicerMinVersion:
                        self.logger.debug("line '%s' is for different slicer version", line)
                    else:
                        version, note = line.split(" ", 1)
                        self.logger.debug("Found version '%s' with note '%s'", version, note)
                        break
            if version != self.vendor.get('config_version', None):
                return version
            else:
                return ""
        except Exception:
            self.logger.exception("Exception, returning error")
            return None


    def download(self, version) -> str:
        if not version:
            self.logger.error("Empty version")
            return None
        updateURL = self.vendor.get('config_update_url', None)
        if not updateURL:
            self.logger.error("Missing 'config_update_url' key")
            return None
        try:
            filename = version + self.VERSION_SUFFIX
            updateURL += filename
            tmpfile = Path(defines.ramdiskPath) / filename
            self.inet.download_url(updateURL, tmpfile)
            return tmpfile
        except Exception:
            self.logger.exception("Exception, returning 'no data'.")
            return None
