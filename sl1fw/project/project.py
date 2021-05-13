# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

# TODO: Fix following pylint problems
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-statements

from __future__ import annotations

import logging
import os
import shutil
import functools
from zipfile import ZipFile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from time import time
from typing import Optional
from enum import unique, IntEnum

import pprint
from PIL import Image
from PySignal import Signal

from sl1fw import defines
from sl1fw.errors.errors import ProjectErrorNotFound, ProjectErrorCantRead, ProjectErrorNotEnoughLayers, \
                                ProjectErrorCorrupted, ProjectErrorAnalysisFailed, ProjectErrorCalibrationInvalid, \
                                ProjectErrorWrongPrinterModel
from sl1fw.errors.warnings import PrintingDirectlyFromMedia, ProjectSettingsModified, VariantMismatch
from sl1fw.configs.project import ProjectConfig
from sl1fw.project.functions import get_white_pixels
from sl1fw.utils.bounding_box import BBox
from sl1fw.api.decorators import range_checked
from sl1fw.libHardware import Hardware


@unique
class LayerCalibrationType(IntEnum):
    NONE = 0
    LABEL_PAD = 1
    LABEL_TEXT = 2


class ProjectLayer:
    def __init__(self, image: str, height_nm: int):
        self.image = image
        self.height_nm = height_nm
        self.times_ms = None
        self.consumed_resin_nl = None
        self.bbox = BBox()
        self.calibration_type = LayerCalibrationType.NONE

    def __repr__(self) -> str:
        items = {
                'image': self.image,
                'height_nm': self.height_nm,
                'times_ms': self.times_ms,
                'consumed_resin_nl': self.consumed_resin_nl,
                'bbox': self.bbox,
                'calibration_type': self.calibration_type,
                }
        pp = pprint.PrettyPrinter(width=196, indent=2)
        return pp.pformat(items)

    def __eq__(self, other):
        return isinstance(other, type(self)) \
            and self.image == other.image \
            and self.height_nm == other.height_nm \
            and self.times_ms == other.times_ms \
            and self.consumed_resin_nl == other.consumed_resin_nl \
            and self.bbox == other.bbox \
            and self.calibration_type == other.calibration_type

    def set_calibration_type(self, total_height_nm, pad_thickness_nm, text_thickness_nm):
        if total_height_nm < pad_thickness_nm:
            self.calibration_type = LayerCalibrationType.LABEL_PAD
        elif total_height_nm < pad_thickness_nm + text_thickness_nm:
            self.calibration_type = LayerCalibrationType.LABEL_TEXT


class Project:
    def __init__(self, hw: Hardware, project_file: str):
        self.logger = logging.getLogger(__name__)
        self._hw = hw
        self.warnings = set()
        self.path = project_file
        self._config = ProjectConfig()
        self.layers = []
        self.total_height_nm = 0
        self.layer_height_nm = 0
        self.layer_height_first_nm = 0
        self.calibrate_text_size_px = 0
        self.calibrate_pad_spacing_px = 0
        self.calibrate_penetration_px = 0
        self.calibrate_compact = False
        self.bbox = BBox()
        self.used_material_nl = 0
        self.modification_time = 0.0
        self.per_partes = hw.config.perPartes
        self._zf: Optional[ZipFile] = None
        self._mode_warn = True
        self._exposure_time_ms = 0
        self._exposure_time_first_ms = 0
        self._layers_slow = 0
        self._layers_fast = 0
        self._calibrate_time_ms = 0
        self._calibrate_time_ms_exact = []
        self._calibrate_regions = 0
        namelist = self._read_toml_config()
        self._parse_config()
        self._build_layers_description(self._check_filenames(namelist))
        self.params_changed = Signal()
        self.path_changed = Signal()

    def __del__(self):
        self.data_close()

    def __repr__(self) -> str:
        items = {
            'path': self.path,
            'layers': self.layers,
            'total_height_nm': self.total_height_nm,
            'layer_height_nm': self.layer_height_nm,
            'layer_height_first_nm': self.layer_height_first_nm,
            'used_material_nl': self.used_material_nl,
            'modification_time': self.modification_time,
            'exposure_time_ms': self._exposure_time_ms,
            'exposure_time_first_ms': self._exposure_time_first_ms,
            'layers_slow': self._layers_slow,
            'layers_fast': self._layers_fast,
            'bbox': self.bbox,
            'calibrate_text_size_px': self.calibrate_text_size_px,
            'calibrate_pad_spacing_px': self.calibrate_pad_spacing_px,
            'calibrate_penetration_px': self.calibrate_penetration_px,
            'calibrate_compact': self.calibrate_compact,
            'calibrate_time_ms': self._calibrate_time_ms,
            'calibrate_time_ms_exact': self._calibrate_time_ms_exact,
            'calibrate_regions': self._calibrate_regions,
            }
        pp = pprint.PrettyPrinter(width=200)
        return "Project:\n" + pp.pformat(items)

    def _read_toml_config(self) -> list:
        self.logger.info("Opening project file '%s'", self.path)
        if not Path(self.path).exists():
            self.logger.error("Project lookup exception: file not found: %s", self.path)
            raise ProjectErrorNotFound
        try:
            zf = ZipFile(self.path, "r")
            self._config.read_text(zf.read(defines.configFile).decode("utf-8"))
            namelist = zf.namelist()
            zf.close()
        except Exception as e:
            self.logger.exception("zip read exception: %s", str(e))
            raise ProjectErrorCantRead from e
        return namelist

    def _check_filenames(self, namelist: list) -> list:
        to_print = []
        for filename in namelist:
            fName, fExt = os.path.splitext(filename)
            if fExt.lower() == ".png" and fName.startswith(self._config.job_dir):
                to_print.append(filename)
        to_print.sort()
        return to_print

    def _parse_config(self):
        # copy visible config values to project internals
        self.logger.debug(self._config)
        self._exposure_time_ms = int(self._config.expTime * 1e3)
        self._exposure_time_first_ms = int(self._config.expTimeFirst * 1e3)
        self._layers_slow = self._config.layersSlow
        self._layers_fast = self._config.layersFast
        if self._config.layerHeight > 0.0099:    # minimal layer height
            self.layer_height_nm = int(self._config.layerHeight * 1e6)
        else:
            # for backward compatibility: 8 mm per turn and stepNum = 40 is 0.05 mm
            self.layer_height_nm = self._hw.config.tower_microsteps_to_nm(self._config.stepnum // (self._hw.config.screwMm / 4))
        self.layer_height_first_nm = int(self._config.layerHeightFirst * 1e6)
        self._calibrate_time_ms = int(self._config.calibrateTime * 1e3)
        self._calibrate_time_ms_exact = [int(x * 1e3) for x in self._config.calibrateTimeExact]
        self._calibrate_regions = self._config.calibrateRegions
        pixel_size_nm = self._hw.exposure_screen.parameters.pixel_size_nm
        self.calibrate_text_size_px = int(self._config.calibrateTextSize * 1e6 // pixel_size_nm)
        self.calibrate_pad_spacing_px = int(self._config.calibratePadSpacing * 1e6 // pixel_size_nm)
        self.calibrate_penetration_px = int(self._config.calibratePenetration * 1e6 // pixel_size_nm)
        self.calibrate_compact = self._config.calibrateCompact
        self.used_material_nl = int(self._config.usedMaterial * 1e6)
        if self._calibrate_regions:
            # labels and pads consumption is ignored
            self.used_material_nl *= self._calibrate_regions
        if self._calibrate_time_ms_exact and len(self._calibrate_time_ms_exact) != self._calibrate_regions:
            self.logger.error("lenght of calibrate_time_ms_exact (%d) not match calibrate_regions (%d)",
                    len(self._calibrate_time_ms_exact), self.calibrate_regions)
            raise ProjectErrorCalibrationInvalid
        if self._config.raw_modification_time:
            try:
                date_time = datetime.strptime(self._config.raw_modification_time, '%Y-%m-%d at %H:%M:%S %Z').replace(tzinfo=timezone.utc)
            except Exception as e:
                self.logger.exception("Cannot parse project modification time: %s", str(e))
                date_time = datetime.now(timezone.utc)
        else:
            date_time = datetime.now(timezone.utc)
        self.modification_time = date_time.timestamp()
        if self._hw.printer_model.name != self._config.printerModel:
            self.logger.error("Wrong printer model '%s', expected '%s'",
                    self._config.printerModel, self._hw.printer_model.name)
            raise ProjectErrorWrongPrinterModel
        if defines.printerVariant != self._config.printerVariant:
            self.warnings.add(VariantMismatch(defines.printerVariant, self._config.printerVariant))
        altered_values = self._config.get_altered_values()
        if altered_values:
            self.warnings.add(ProjectSettingsModified(altered_values))

    def _build_layers_description(self, to_print: list):
        first = True
        pad_thickness_nm = int(self._config.calibratePadThickness * 1e6)
        text_thickness_nm = int(self._config.calibrateTextThickness * 1e6)
        for image in to_print:
            if first:
                height = self.layer_height_first_nm
                first = False
            else:
                height = self.layer_height_nm
            layer = ProjectLayer(image, height)
            layer.set_calibration_type(self.total_height_nm, pad_thickness_nm, text_thickness_nm)
            self.layers.append(layer)
            self.total_height_nm += height
        total_layers = len(self.layers)
        self.logger.info("found %d layer(s)", total_layers)
        if not total_layers:
            self.logger.error("Not enough layers")
            raise ProjectErrorNotEnoughLayers
        self._fill_layers_times()

    def _fill_layers_times(self):
        time_loss = (self._exposure_time_first_ms - self._exposure_time_ms) // (self._config.fadeLayers + 1)
        extra_layers = defines.exposure_time_first_extra_layers
        for i in range(len(self.layers)):
            if i <= extra_layers:
                times = [self._exposure_time_first_ms]
            elif i <= self._config.fadeLayers + extra_layers:
                times = [self._exposure_time_first_ms - (i - extra_layers) * time_loss]
            else:
                times = [self._exposure_time_ms]
            if self._calibrate_regions:
                if self._calibrate_time_ms_exact:
                    times = self._calibrate_time_ms_exact
                else:
                    times.extend([self._calibrate_time_ms] * (self._calibrate_regions - 1))
            self.layers[i].times_ms = times

    def analyze(self, force: bool = False ):
        """
        Analyze project and fill layer's 'bbox' and 'consumed_resin_nl' where needed

        :param force: get new values and overwrite existing
        """
        self.logger.info("analyze started")
        start_time = time()
        new_slow_layers = 0
        new_used_material_nl = 0
        update_consumed = False
        self.bbox = BBox()
        try:
            for layer in self.layers:
                if force or not layer.bbox or not layer.consumed_resin_nl:
                    img = self.read_image(layer.image)
                else:
                    img = None
                if force or not layer.bbox:
                    layer.bbox = BBox(img.getbbox())
                    self.logger.debug("'%s' image bbox: %s", layer.image, layer.bbox)
                else:
                    self.logger.debug("'%s' project bbox: %s", layer.image, layer.bbox)
                self.bbox.maximize(layer.bbox)
                # labels and pads are not counted
                if force or not layer.consumed_resin_nl:
                    white_pixels = get_white_pixels(img.crop(layer.bbox.coords))
                    if self._calibrate_regions:
                        white_pixels *= self._calibrate_regions
                    self.logger.debug("white_pixels: %s", white_pixels)
                    update_consumed = True
                    if white_pixels > self._hw.white_pixels_threshold:
                        new_slow_layers += 1
                    # nm3 -> nl
                    layer.consumed_resin_nl = white_pixels * self._hw.exposure_screen.parameters.pixel_size_nm ** 2 * layer.height_nm // int(1e15)
                    new_used_material_nl += layer.consumed_resin_nl
            self.logger.info("analyze done in %f secs, result: %s", time() - start_time, self.bbox)
            if update_consumed:
                self._layers_slow = new_slow_layers
                self._layers_fast = len(self.layers) - new_slow_layers
                self.used_material_nl = new_used_material_nl
                self.logger.info("new layers_slow: %d, new layers_fast: %s", self._layers_slow, self._layers_fast)
                self.logger.info("new used_material_nl: %d", self.used_material_nl)
        except Exception as e:
            self.logger.exception("analyze exception: %s", str(e))
            raise ProjectErrorAnalysisFailed from e

    @property
    def name(self) -> str:
        """
        Name of the project

        This is basename of the original project filename.

        :return: Name of the project as string
        """
        return Path(self.path).stem

    @property
    def exposure_time_ms(self) -> int:
        return self._exposure_time_ms

    @range_checked(defines.exposure_time_min_ms, defines.exposure_time_max_ms)
    @exposure_time_ms.setter
    def exposure_time_ms(self, value: int) -> None:
        if self._exposure_time_ms != value:
            self._exposure_time_ms = value
            self._fill_layers_times()
            self.params_changed.emit()

    @property
    def exposure_time_first_ms(self) -> int:
        return self._exposure_time_first_ms

    @range_checked(defines.exposure_time_first_min_ms, defines.exposure_time_first_max_ms)
    @exposure_time_first_ms.setter
    def exposure_time_first_ms(self, value: int) -> None:
        if self._exposure_time_first_ms != value:
            self._exposure_time_first_ms = value
            self._fill_layers_times()
            self.params_changed.emit()

    # FIXME compatibility with api/standard0
    @property
    def exposure_time_calibrate_ms(self) -> int:
        return self._calibrate_time_ms

    @property
    def calibrate_time_ms(self) -> int:
        return self._calibrate_time_ms

    @range_checked(defines.exposure_time_calibrate_min_ms, defines.exposure_time_calibrate_max_ms)
    @calibrate_time_ms.setter
    def calibrate_time_ms(self, value: int) -> None:
        if self._calibrate_time_ms != value:
            self._calibrate_time_ms = value
            self._fill_layers_times()
            self.params_changed.emit()

    # FIXME compatibility with api/standard0
    @property
    def calibration_regions(self) -> int:
        return self._calibrate_regions

    @property
    def calibrate_regions(self) -> int:
        return self._calibrate_regions

    @calibrate_regions.setter
    def calibrate_regions(self, value: int) -> None:
        if value not in [0, 2, 4, 6, 8, 9, 10]:
            self.logger.error("calibrate_regions - value %d not in [0, 2, 4, 6, 8, 9, 10]", value)
            raise ProjectErrorCalibrationInvalid
        if self._calibrate_regions != value:
            self._calibrate_regions = value
            self._fill_layers_times()
            self.params_changed.emit()

    @property
    def total_layers(self) -> int:
        total_layers = len(self.layers)
        if total_layers != self._layers_slow + self._layers_fast:
            self.logger.warning("total_layers (%d) not match layers_slow (%d) + layers_fast (%d)",
                    total_layers, self._layers_slow, self._layers_fast)
        return total_layers

    # TODO use nl everywhere
    @property
    def used_material(self):
        return self.used_material_nl / 1e6

    def copy_and_check(self):
        origin_path = os.path.normpath(self.path)
        (dummy, filename) = os.path.split(origin_path)
        new_source = os.path.join(defines.previousPrints, filename)
        if origin_path == new_source:
            self.logger.debug("Reprint of project '%s'", origin_path)
        elif origin_path.startswith(defines.internalProjectPath):
            self.logger.debug("Internal storage project, creating symlink '%s' -> '%s'", origin_path, new_source)
            os.symlink(origin_path, new_source)
            self.path = new_source
            self.path_changed.emit(self.path)
        else:
            statvfs = os.statvfs(os.path.dirname(defines.previousPrints))
            size_available = statvfs.f_frsize * statvfs.f_bavail - defines.internalReservedSpace
            self.logger.debug("Internal storage available space: %d bytes", size_available)
            try:
                filesize = os.path.getsize(self.path)
                self.logger.debug("Project size: %d bytes", filesize)
            except Exception as e:
                self.logger.exception("filesize exception: %s", str(e))
                raise ProjectErrorCantRead from e
            if size_available < filesize:
                self.logger.warning("Not enough free space, printing directly from USB.")
                self.warnings.add(PrintingDirectlyFromMedia())
            else:
                try:
                    self.logger.debug("Copying project to internal storage '%s' -> '%s'", origin_path, new_source)
                    shutil.copyfile(origin_path, new_source)
                    self.path = new_source
                    self.path_changed.emit(self.path)
                except Exception as e:
                    self.logger.exception("copyfile exception: %s", str(e))
                    self.logger.warning("Can't copy the project, printing directly from USB.")
                    self.warnings.add(PrintingDirectlyFromMedia())
        try:
            zf = ZipFile(self.path, "r")
            badfile = zf.testzip()
            zf.close()
        except Exception as e:
            self.logger.exception("zip read exception: %s", str(e))
            raise ProjectErrorCantRead from e
        if badfile is not None:
            self.logger.error("Corrupted file: %s", badfile)
            raise ProjectErrorCorrupted
        # TODO verify layers[]['image'] in zip files

    def read_image(self, filename: str):
        ''' may raise ZipFile exception '''
        self.data_open()
        self.logger.debug("loading '%s' from '%s'", filename, self.path)
        img = Image.open(BytesIO(self._zf.read(filename)))
        if img.mode != "L":
            if self._mode_warn:
                self.logger.warning("Image '%s' is in '%s' mode, should be 'L' (grayscale without alpha)."
                                    " Losing time in conversion. This is reported only once per project.",
                                    filename, img.mode)
                self._mode_warn = False
            img = img.convert("L")
        return img

    def data_open(self):
        ''' may raise ZipFile exception '''
        if not self._zf:
            self._zf = ZipFile(self.path, "r")

    def data_close(self):
        if self._zf:
            self._zf.close()

    @functools.lru_cache(maxsize=1)
    def count_remain_time(self, layers_done: int = 0, slow_layers_done: int = 0) -> int:
        time_remain_ms = sum(sum(x.times_ms) for x in self.layers[layers_done:])
        total_layers = len(self.layers)
        slow_layers = self._layers_slow - slow_layers_done
        if slow_layers < 0:
            slow_layers = 0
        fast_layers = total_layers - layers_done - slow_layers
        time_remain_ms += fast_layers * self._hw.config.tiltFastTime
        time_remain_ms += slow_layers * self._hw.config.tiltSlowTime
        time_remain_ms += (total_layers - layers_done) * (
                self.layer_height_nm * 5000 / 1000 / 1000  # tower move
                + self._hw.config.delayBeforeExposure * 100
                + self._hw.config.delayAfterExposure * 100)
        self.logger.debug("time_remain_ms: %f", time_remain_ms)
        return int(time_remain_ms)

    def set_timings_reference(self, project: Project):
        """
        Set times from existing project without range checks

        Used for reprint. As we load times from projects without checking there needs to be a way how to reprint using
        the same settings.
        """
        self._exposure_time_ms = project.exposure_time_ms
        self._exposure_time_first_ms = project.exposure_time_first_ms
        self._calibrate_time_ms = project.calibrate_time_ms

    @property
    def is_open(self):
        return self._zf and self._zf.fp
