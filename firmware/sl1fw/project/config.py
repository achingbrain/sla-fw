# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw.libConfig import Config, FloatValue, IntValue, TextValue, IntListValue
from sl1fw import defines


class ProjectConfig(Config):
    """
    Project configuration is read from config.ini located in the project zip file. Currently the content is parsed using
    a Toml parser with preprocessor that adjusts older custom configuration format if necessary. Members describe
    possible configuration options. These can be set using the

    key = value

    notation. For details see Toml format specification: https://en.wikipedia.org/wiki/TOML
    """

    def __init__(self):
        super().__init__(is_master=True)

    job_dir = TextValue("no project", key="jobDir", doc="Name of the directory containing layer images.")

    expTime = FloatValue(8.0, doc="Exposure time. [s]")
    expTime2 = FloatValue(lambda self: self.expTime, doc="Exposure time 2. [s]")
    expTime3 = FloatValue(lambda self: self.expTime, doc="Exposure time 3. [s]")
    expTimeFirst = FloatValue(35.0, doc="First layer exposure time. [s]")

    layerHeight = FloatValue(-1, doc="Layer height, if not equal to -1 supersedes stepNum. [mm]")
    layerHeight2 = FloatValue(
        lambda self: self.layerHeight, doc="Layer height 2, if not equal to -1 supersedes stepNum2. [mm]"
    )
    layerHeight3 = FloatValue(
        lambda self: self.layerHeight, doc="Layer height 3, if not equal to -1 supersedes stepNum3. [mm]"
    )

    stepnum = IntValue(40, doc="Layer height [microsteps]")
    stepnum2 = IntValue(lambda self: self.stepnum, doc="Layer height 2 [microsteps]")
    stepnum3 = IntValue(lambda self: self.stepnum, doc="Layer height 3 [microsteps]")

    layerHeightFirst = FloatValue(0.05)

    slice2 = IntValue(9999998, doc="Layer number defining switch to parameters 2.")
    slice3 = IntValue(9999999, doc="Layer number defining switch to parameters 3.")
    fadeLayers = IntValue(
        10,
        minimum=3,
        maximum=200,
        key="numFade",
        doc="Number of layers used for transition from first layer exposure time to standard exposure time.",
    )

    calibrateTime = FloatValue(
        1.0, doc="Time added to exposure per calibration region. [seconds]"
    )
    calibrateRegions = IntValue(0, doc="Number of calibration regions (2, 4, 6, 8, 9, 10), 0 = off")
    raw_calibrate_text_size = FloatValue(
        5.0, key="calibrateTextSize", doc="Size of the text on calibration label. [millimeters]"
    )
    raw_calibrate_text_thickness = FloatValue(
        0.5, key="calibrateTextThickness", doc="Thickness of the text on calibration label. [millimeters]"
    )
    raw_calibrate_pad_spacing = FloatValue(
        1.0, key="calibratePadSpacing", doc="Spacing of the pad around the text. [millimeters]"
    )
    raw_calibrate_pad_thickness = FloatValue(
        0.5, key="calibratePadThickness", doc="Thickness of the pad of the calibration label. [millimeters]"
    )
    raw_calibrate_penetration = FloatValue(
        0.5, key="calibratePenetration", doc="How much to sink the calibration label into the object. [millimeters]"
    )
    raw_calibrate_bbox = IntListValue(
        None, key="calibrateBBox", doc="Bounding box of calibration object: xmin, ymin, xmax, ymax. [pixels]"
    )
    raw_first_layer_bbox = IntListValue(
        None, key="firstLayerBBox", doc="Bounding box of first layer of calibration object: xmin, ymin, xmax, ymax. [pixels]"
    )

    usedMaterial = FloatValue(
        defines.resinMaxVolume - defines.resinMinVolume,
        doc="Resin necessary to print the object. Default is full tank. [milliliters]",
    )
    layersSlow = IntValue(0, key="numSlow", doc="Number of layers that require slow tear off.")
    layersFast = IntValue(0, key="numFast", doc="Number of layers that do not require slow tear off.")

    action = TextValue(doc="What to do with the project. Legacy value, currently discarded.")
    raw_modification_time = TextValue(
            None, key="fileCreationTimestamp", doc="Date and time of project creation [YYYY-MM-DD at HH:MM:SS TZ]")

    printProfile = TextValue(doc="Print settings used for slicing, currently discarded.")
    materialName = TextValue(doc="Material used for slicing, currently discarded.")
    printerProfile = TextValue(doc="Printer settings used for slicing, currently discarded.")
    printerModel = TextValue(defines.slicerPrinterModel, doc="Printer model project is sliced for.")
    printerVariant = TextValue(defines.slicerPrinterVariant, doc="Printer variant project is sliced for.")
    printTime = FloatValue(0.0, doc="Project print time, currently discarded (calculated by fw) [seconds]")
    prusaSlicerVersion = TextValue(doc="Slicer used for slicing, currently discarded.")
