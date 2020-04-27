# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# TODO: Fix following pylint problems
# pylint: disable=no-else-return
# pylint: disable=too-many-public-methods
# pylint: disable=too-many-instance-attributes

import logging
import os
import shutil
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from time import time

import numpy
from PIL import Image

from sl1fw import defines
from sl1fw.libConfig import HwConfig
from sl1fw.project.config import ProjectConfig
from sl1fw.project.functions import get_white_pixels
from sl1fw.states.project import ProjectState


class Project:

    def __init__(self, hw_config: HwConfig):
        self.logger = logging.getLogger(__name__)
        self.config = ProjectConfig()
        self._hw_config = hw_config
        self.origin = None
        self.source = None
        self.zf = None
        self.mode_warn = True
        self.state = ProjectState.UNINITIALIZED
        self.to_print = []
        self._total_layers = 0
        self._calibrate_areas = []
        self._calibrate_bbox = None
        self._first_layer_bbox = None

    def __del__(self):
        self.data_close()

    def __str__(self):
        res = [f"origin: {self.origin}", f"source: {self.source}", f"to_print: {self.to_print}"]
        return str(self.config) + "\n\t" + "\n\t".join(res)

    def as_dictionary(self):
        project_data = {
                'origin': self.origin,
                'source': self.source,
                'to_print': self.to_print,
                }
        for key, val in vars(self.__class__).items():
            if isinstance(val, property):
                project_data[key] = getattr(self, key)
        return project_data

    def read(self, project_file: str) -> ProjectState:
        self.state = self._read(project_file)
        return self.state

    def _read(self, project_file: str) -> ProjectState:
        self.logger.debug("Opening project file '%s'", project_file)
        self.origin = None
        self.source = None
        self.mode_warn = True
        self.to_print = []
        self._calibrate_areas = []
        self._calibrate_bbox = None
        self._first_layer_bbox = None

        if not Path(project_file).exists():
            self.logger.error("Project lookup exception: file not exists: %s", project_file)
            return ProjectState.NOT_FOUND

        try:
            zf = zipfile.ZipFile(project_file, "r")
            self.config.read_text(zf.read(defines.configFile).decode("utf-8"))
            namelist = zf.namelist()
            zf.close()
        except Exception as e:
            self.logger.exception("zip read exception: %s", str(e))
            return ProjectState.CANT_READ

        # Set paths
        self.origin = self.source = project_file

        for filename in namelist:
            fName, fExt = os.path.splitext(filename)
            if fExt.lower() == ".png" and fName.startswith(self.config.job_dir):
                self.to_print.append(filename)

        self.to_print.sort()
        self._total_layers = len(self.to_print)

        self.logger.debug("found %d layer(s)", self._total_layers)
        if not self._total_layers:
            return ProjectState.NOT_ENOUGH_LAYERS
        return ProjectState.OK

    @property
    def name(self) -> str:
        """
        Name of the project

        This is basename of the original project filename.

        :return: Name of the project as string
        """
        return Path(self.origin).stem

    @property
    def expTime(self) -> float:
        return self.config.expTime

    @expTime.setter
    def expTime(self, value: float) -> None:
        self.config.expTime = value
        self._calibrate_areas = []

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
        if self.config.layerHeight > 0.0099:    # min layer height
            return self._hw_config.calcMicroSteps(self.config.layerHeight)
        else:
            # for backward compatibility: 8 mm per turn and stepNum = 40 is 0.05 mm
            return self.config.stepnum / (self._hw_config.screwMm / 4)

    @property
    def layerMicroSteps2(self) -> int:
        if self.config.layerHeight2 > 0.0099:   # min layer height
            return self._hw_config.calcMicroSteps(self.config.layerHeight2)
        else:
            # for backward compatibility: 8 mm per turn and stepNum = 40 is 0.05 mm
            return self.config.stepnum2 / (self._hw_config.screwMm / 4)

    @property
    def layerMicroSteps3(self) -> int:
        if self.config.layerHeight3 > 0.0099:   # min layer height
            return self._hw_config.calcMicroSteps(self.config.layerHeight3)
        else:
            # for backward compatibility: 8 mm per turn and stepNum = 40 is 0.05 mm
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
        self._calibrate_areas = []

    @property
    def calibrateRegions(self) -> int:
        return self.config.calibrateRegions

    @calibrateRegions.setter
    def calibrateRegions(self, value: int) -> None:
        if value not in [0, 2, 4, 6, 8, 9, 10]:
            raise ValueError("Value %d not in [0, 2, 4, 6, 8, 9, 10]" % value)
        self.config.calibrateRegions = value
        self._calibrate_areas = []

    @property
    def calibrateTextSize(self) -> int:
        return int(self.config.raw_calibrate_text_size / defines.screenPixelSize)

    @property
    def calibrateTextThickness(self) -> int:
        return int(self.config.raw_calibrate_text_thickness / self._hw_config.calcMM(self.layerMicroSteps))

    @property
    def calibratePadSpacing(self) -> int:
        return int(self.config.raw_calibrate_pad_spacing / defines.screenPixelSize)

    @property
    def calibratePadThickness(self) -> int:
        return int(self.config.raw_calibrate_pad_thickness / self._hw_config.calcMM(self.layerMicroSteps))

    @property
    def calibratePenetration(self) -> int:
        return int(self.config.raw_calibrate_penetration / defines.screenPixelSize)

    @property
    def firsLayerBBox(self) -> list:
        if self.calibrateRegions and not self._first_layer_bbox:
            bbox = self._check_bbox(self.config.raw_first_layer_bbox)
            if bbox:
                self._first_layer_bbox = bbox
            else:
                try:
                    img = self.read_image(self.to_print[0])
                    self._first_layer_bbox = list(img.getbbox())
                    self.logger.debug("first layer bbox analyze done, result: %s", str(self._first_layer_bbox))
                except Exception as e:
                    self.logger.exception("bbox analyze exception: %s", str(e))
                    # FIXME warn user (calibration will not work)
        return self._first_layer_bbox

    @firsLayerBBox.setter
    def firsLayerBBox(self, value: list):
        self.config.raw_first_layer_bbox = self._first_layer_bbox = value

    @property
    def calibrateBBox(self) -> list:
        if self.calibrateRegions and not self._calibrate_bbox:
            bbox = self._check_bbox(self.config.raw_calibrate_bbox)
            if bbox:
                self._calibrate_bbox = bbox
            else:
                self.logger.debug("bbox analyze started")
                start_time = time()
                np_array = numpy.array([], numpy.int32)
                new_slow_layers = 0
                try:
                    # every second image (it's faster and it should be enough)
                    for filename in self.to_print[::2]:
                        img = self.read_image(filename)
                        bbox = img.getbbox()
                        self.logger.debug("'%s' bbox: %s", filename, bbox)
                        np_array = numpy.append(np_array, bbox)
                        # TODO labels and pads are ignored, does we need them?
                        white_pixels = get_white_pixels(img.crop(bbox)) * self.calibrateRegions
                        self.logger.debug("white_pixels: %s", white_pixels)
                        if white_pixels > self._hw_config.whitePixelsThd:
                            new_slow_layers += 2
                    np_array = numpy.reshape(np_array, (np_array.size//4, 2, 2))
                    minval = np_array.min(axis = 0)
                    maxval = np_array.max(axis = 0)
                    self._calibrate_bbox = [minval[0][0], minval[0][1], maxval[1][0], maxval[1][1]]
                    self.logger.debug("bbox analyze done in %f secs, result: %s", time() - start_time, str(self._calibrate_bbox))
                    self.config.layersSlow = new_slow_layers
                    self.config.layersFast = self._total_layers - new_slow_layers
                    self.logger.debug("new layersSlow: %d, new layersFast: %s", self.config.layersSlow, self.config.layersFast)
                except Exception as e:
                    self.logger.exception("bbox analyze exception: %s", str(e))
                    # FIXME warn user (calibration will not work)
        return self._calibrate_bbox

    @calibrateBBox.setter
    def calibrateBBox(self, value: list):
        self.config.raw_calibrate_bbox = self._calibrate_bbox = value

    @property
    def calibrateAreas(self):
        if not self.config.calibrateRegions or self._calibrate_areas:
            return self._calibrate_areas

        self._calibrate_areas = []
        areaMap = {
                2 : (2, 1),
                4 : (2, 2),
                6 : (3, 2),
                8 : (4, 2),
                9 : (3, 3),
                10 : (10, 1),
                }
        if self.config.calibrateRegions not in areaMap:
            self.logger.error("bad value calibrateRegions (%d)", self.config.calibrateRegions)
            return []

        divide = areaMap[self.config.calibrateRegions]
        if defines.screenWidth > defines.screenHeight:
            x = 0
            y = 1
        else:
            x = 1
            y = 0

        stepW = defines.screenWidth // divide[x]
        stepH = defines.screenHeight // divide[y]

        lw = 0
        etime = self.config.expTime
        for i in range(divide[x]):
            lh = 0
            w = 0
            for j in range(divide[y]):
                w = (i+1) * stepW
                h = (j+1) * stepH
                rect = {'x': lw, 'y': lh, 'w': stepW, 'h': stepH}
                self.logger.debug("%.1f - %s", etime, str(rect))
                self._calibrate_areas.append({ 'time': etime, 'rect': rect, 'stripe': self.config.calibrateRegions == 10})
                etime += self.config.calibrateTime
                lh = h
            lw = w
        return self._calibrate_areas

    @property
    def usedMaterial(self) -> float:
        used = self.config.usedMaterial
        if self.config.calibrateRegions:
            # label consumption is ignored
            used *= self.config.calibrateRegions
        return used

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
                self.logger.exception("Cannot parse project modification time: %s", str(e))
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

    def copy_and_check(self):
        state = ProjectState.OK
        # check free space
        statvfs = os.statvfs(defines.ramdiskPath)
        ramdisk_available = statvfs.f_frsize * statvfs.f_bavail - defines.ramdiskReservedSpace
        self.logger.debug("Ramdisk available space: %d bytes", ramdisk_available)
        try:
            filesize = os.path.getsize(self.origin)
            self.logger.debug("Zip file size: %d bytes", filesize)
        except Exception:
            self.logger.exception("filesize exception:")
            return ProjectState.CANT_READ
        try:
            if ramdisk_available < filesize:
                raise Exception("Not enough free space in the ramdisk!")
            (dummy, filename) = os.path.split(self.origin)
            new_source = os.path.join(defines.ramdiskPath, filename)
            if os.path.normpath(new_source) != os.path.normpath(self.origin):
                shutil.copyfile(self.origin, new_source)
            self.source = new_source
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

    def read_image(self, filename: str):
        ''' may raise ZipFile exception '''
        self.data_open()
        self.logger.debug("loading '%s' from '%s'", filename, self.source)
        img = Image.open(BytesIO(self.zf.read(filename)))
        if img.mode != "L":
            if self.mode_warn:
                self.logger.warning("Image '%s' is in '%s' mode, should be 'L' (grayscale without alpha)."
                                    " Losing time in conversion. This is reported only once per project.",
                                    filename, img.mode)
                self.mode_warn = False
            img = img.convert("L")
        return img

    def data_open(self):
        ''' may raise ZipFile exception '''
        if not self.zf:
            self.zf = zipfile.ZipFile(self.source, "r")

    def data_close(self):
        if self.zf:
            self.zf.close()

    def _check_bbox(self, bbox: list):
        if not bbox:
            return None

        if len(bbox) != 4 or bbox[2] < bbox[0] or bbox[3] < bbox[1]:
            self.logger.warning("bbox %s is not a rectangle", str(bbox))
            return None

        if (not 0 <= bbox[0] <= defines.screenWidth
                or not 0 <= bbox[1] <= defines.screenHeight
                or not 0 <= bbox[2] <= defines.screenWidth
                or not 0 <= bbox[3] <= defines.screenHeight):
            self.logger.warning("bbox %s is out of range [0,%d,0,%d]",
                                str(bbox), defines.screenWidth, defines.screenHeight)
            return None

        return bbox

    def count_remain_time(self, layers_done: int = 0, slow_layers_done: int = 0) -> int:
        time_remain = 0
        slow_layers = self.config.layersSlow - slow_layers_done
        if slow_layers < 0:
            slow_layers = 0
        fast_layers = self._total_layers - layers_done - slow_layers
        # first 3 layers with expTimeFirst
        long1 = 3 - layers_done
        if long1 > 0:
            time_remain += long1 * (self.expTimeFirst - self.expTime)
        #endif
        # fade layers (approx)
        long2 = self.fadeLayers + 3 - layers_done
        if long2 > 0:
            time_remain += long2 * ((self.expTimeFirst - self.expTime) / 2 - self.expTime)
        #endif
        time_remain += fast_layers * self._hw_config.tiltFastTime
        time_remain += slow_layers * self._hw_config.tiltSlowTime

        # FIXME slice2 and slice3
        time_remain += (fast_layers + slow_layers) * (
                self.calibrateRegions * self.calibrateTime
                + self._hw_config.calcMM(self.layerMicroSteps) * 5  # tower move
                + self.expTime
                + self._hw_config.delayBeforeExposure
                + self._hw_config.delayAfterExposure)
        self.logger.debug("time_remain: %f", time_remain)
        return int(round(time_remain / 60))
