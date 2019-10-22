# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from enum import IntEnum, unique
import zipfile

from sl1fw import defines
from sl1fw.libConfig import HwConfig
from sl1fw.project.config import ProjectConfig


@unique
class ProjectState(IntEnum):
    OK = 0
    NOT_FOUND = 1
    CANT_READ = 2
    NOT_ENOUGH_LAYERS = 3
    CORRUPTED = 4
    PRINT_DIRECTLY = 5


class Project:

    def __init__(self, hw_config: HwConfig):
        self.logger = logging.getLogger(__name__)
        self.config = ProjectConfig()
        self._hw_config = hw_config
        self.origin = None
        self.source = None
        self.to_print = []
        self._total_layers = 0

    def __str__(self):
        return str(self.config)

    def read(self, project_file: str) -> ProjectState:
        self.logger.debug("Opening project file '%s'", project_file)

        if not Path(project_file).exists():
            self.logger.error("Project lookup exception: file not exists: " + project_file)
            return ProjectState.NOT_FOUND

        try:
            zf = zipfile.ZipFile(project_file, "r")
            self.config.read_text(zf.read(defines.configFile).decode("utf-8"))
            namelist = zf.namelist()
            zf.close()
        except Exception as e:
            self.logger.exception("zip read exception:" + str(e))
            return ProjectState.CANT_READ

        # Set paths
        self.origin = self.source = project_file

        for filename in namelist:
            fName, fExt = os.path.splitext(filename)
            if fExt.lower() == ".png" and fName.startswith(self.config.projectName):
                self.to_print.append(filename)

        self.to_print.sort()
        self._total_layers = len(self.to_print)

        self.logger.debug("found %d layers", self._total_layers)
        if self._total_layers < 2:
            return ProjectState.NOT_ENOUGH_LAYERS
        return ProjectState.OK

    @property
    def name(self) -> str:
        return self.config.projectName

    @property
    def expTime(self) -> float:
        return self.config.expTime

    @expTime.setter
    def expTime(self, value: float) -> None:
        self.config.expTime = value

    @property
    def expTime2(self) -> float:
        return self.config.expTime2

    @property
    def expTime3(self) -> float:
        return self.config.expTime3

    @property
    def expTimeFirst(self) -> float:
        return self.config.expTimeFirst

    @expTimeFirst.setter
    def expTimeFirst(self, value: float) -> None:
        self.config.expTimeFirst = value

    @property
    def layerMicroSteps(self) -> int:
        if self.config.layerHeight > 0.0099:
            return self._hw_config.calcMicroSteps(self.config.layerHeight)
        else:
            # historicky zmatlano aby sedelo ze pri 8 mm na otacku stepNum = 40 odpovida 0.05 mm
            return self.config.stepnum / (self._hw_config.screwMm / 4)

    @property
    def layerMicroSteps2(self) -> int:
        if self.config.layerHeight2 > 0.0099:
            return self._hw_config.calcMicroSteps(self.config.layerHeight2)
        else:
            # historicky zmatlano aby sedelo ze pri 8 mm na otacku stepNum = 40 odpovida 0.05 mm
            return self.config.stepnum2 / (self._hw_config.screwMm / 4)

    @property
    def layerMicroSteps3(self) -> int:
        if self.config.layerHeight3 > 0.0099:
            return self._hw_config.calcMicroSteps(self.config.layerHeight3)
        else:
            # historicky zmatlano aby sedelo ze pri 8 mm na otacku stepNum = 40 odpovida 0.05 mm
            return self.config.stepnum3 / (self._hw_config.screwMm / 4)

    @property
    def layerMicroStepsFirst(self) -> int:
        return self._hw_config.calcMicroSteps(self.config.layerHeightFirst)

    @property
    def slice2(self) -> int:
        return self.config.slice2

    @property
    def slice3(self) -> int:
        return self.config.slice3

    @property
    def fadeLayers(self) -> int:
        return self.config.fadeLayers

    @property
    def calibrateTime(self) -> float:
        return self.config.calibrateTime

    @calibrateTime.setter
    def calibrateTime(self, value: float) -> None:
        self.config.calibrateTime = value

    @property
    def calibrateRegions(self) -> int:
        return self.config.calibrateRegions

    @property
    def calibrateInfoLayers(self) -> int:
        return self.config.calibrateInfoLayers

    @property
    def calibratePenetration(self) -> int:
        return int(self.config.raw_calibrate_penetration / defines.screenPixelSize)

    @property
    def usedMaterial(self) -> float:
        return self.config.usedMaterial

    @property
    def layersSlow(self) -> int:
        return self.config.layersSlow

    @property
    def layersFast(self) -> int:
        return self.config.layersFast

    @property
    def totalLayers(self) -> int:
        if self._total_layers != self.config.layersSlow + self.config.layersFast:
            self.logger.warning("totalLayers (%d) not match layersSlow (%d) + layersFast (%d)", self._total_layers,
                                self.config.layersSlow, self.config.layersFast)
        return self._total_layers

    @property
    def modificationTime(self) -> float:
        if self.config.raw_modification_time:
            try:
                date_time = datetime.strptime(self.config.raw_modification_time, '%Y-%m-%d at %H:%M:%S %Z').replace(tzinfo=timezone.utc)
            except Exception as e:
                self.logger.exception("Cannot parse project modification time: " + str(e))
                date_time = datetime.now(timezone.utc)
        else:
            date_time = datetime.now(timezone.utc)
        return date_time.timestamp()

    @property
    def printerModel(self) -> str:
        return self.config.printerModel

    @property
    def printerVariant(self) -> str:
        return self.config.printerVariant


    def copyAndCheck(self):
        state = ProjectState.OK
        # check free space
        statvfs = os.statvfs(defines.ramdiskPath)
        ramdisk_available = statvfs.f_frsize * statvfs.f_bavail - defines.ramdiskReservedSpace
        self.logger.debug("Ramdisk available space: %d bytes" % ramdisk_available)
        try:
            filesize = os.path.getsize(self.origin)
            self.logger.debug("Zip file size: %d bytes" % filesize)
        except Exception:
            self.logger.exception("filesize exception:")
            return ProjectState.CANT_READ

        try:
            if ramdisk_available < filesize:
                raise Exception("Not enough free space in the ramdisk!")
            (dummy, filename) = os.path.split(self.origin)
            newSource = os.path.join(defines.ramdiskPath, filename)
            if os.path.normpath(newSource) != os.path.normpath(self.origin):
                shutil.copyfile(self.origin, newSource)
            self.source = newSource
        except Exception:
            self.logger.exception("copyfile exception:")
            state = ProjectState.PRINT_DIRECTLY

        try:
            zf = zipfile.ZipFile(self.source, "r")
            badfile = zf.testzip()
            zf.close()
            if badfile is not None:
                self.logger.error("Corrupted file: %s", badfile)
                return ProjectState.CORRUPTED
        except Exception:
            self.logger.exception("zip read exception:")
            return ProjectState.CANT_READ

        return state
