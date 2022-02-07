# This file is part of the SLA firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# Copyright (C) 2020-2021 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import List

from slafw import defines
from slafw.configs.ini import Config
from slafw.configs.value import BoolValue, IntValue, IntListValue, FloatValue, TextValue


class HwConfig(Config):
    # pylint: disable=R0902
    """
       Hardware configuration is read from /etc/sl1fw/hardware.cfg . Currently the content is parsed using a Toml
       parser with preprocessor that adjusts older custom configuration format if necessary. Members describe
       possible configuration options. These can be set using the

       key = value

       notation. For details see Toml format specification: https://en.wikipedia.org/wiki/TOML
    """

    def calcMicroSteps(self, mm: float) -> int:
        """
        Convert from millimeters to microsteps using current tower pitch.

        :param mm: Tower position in millimeters
        :return: Tower position in microsteps
        """
        return int(mm * self.microStepsMM)

    def calcMM(self, microSteps: int) -> float:
        """
        Convert microsteps to millimeters using current tower pitch.

        :param microSteps: Tower position in microsteps
        :return: Tower position in millimeters
        """
        return round(float(microSteps) / self.microStepsMM, 3)

    def tower_microsteps_to_nm(self, microsteps: int) -> int:
        """
        Covert microsteps to nanometers using the current tower pitch

        :param microsteps: Tower position in microsteps
        :return: Tower position in nanometers
        """
        return self.tower_microstep_size_nm * microsteps

    def nm_to_tower_microsteps(self, nanometers: int) -> int:
        """
        Covert nanometers to microsteps using the current tower pitch

        :param nanometers: Tower position in nanometers
        :return: Tower position in microsteps
        """
        return nanometers // self.tower_microstep_size_nm

    fanCheck = BoolValue(True, doc="Check fan function if set to True.")
    coverCheck = BoolValue(True, doc="Check for closed cover during printer movements and exposure if set to True.")
    MCversionCheck = BoolValue(True, doc="Check motion controller firmware version if set to True.")
    resinSensor = BoolValue(True, doc="If True the the resin sensor will be used to measure resin level before print.")
    autoOff = BoolValue(True, doc="If True the printer will be shut down after print.")
    mute = BoolValue(False, doc="Mute motion controller speaker if set to True.")
    screwMm = IntValue(4, doc="Pitch of the tower/platform screw. [mm]")

    @property
    def microStepsMM(self) -> float:
        """
        Get number of microsteps per millimeter using current tower screw pitch.

        :return: Number of microsteps per one millimeter
        """
        return 200 * 16 / int(self.screwMm)

    @property
    def tower_microstep_size_nm(self) -> int:
        """
        Get microstep width in nanometers

        :return: Width in nanometers
        """
        return (self.screwMm * 1000 * 1000) // (200 * 16)

    # tilt related
    tilt = BoolValue(True, doc="Use tilt to tear off the layers.")
    tiltSensitivity = IntValue(0, minimum=-2, maximum=2, doc="Tilt sensitivity adjustment")
    tiltHeight = IntValue(defines.defaultTiltHeight, doc="Position of the leveled tilt. [ustep]")
    tiltMax = IntValue(defines.tiltMax, doc="Max position allowed. It shoud corespond to the top deadlock of the axis. [ustep]")
    tiltMin = IntValue(defines.tiltMin, doc="Position used to ensure the tilt ends at the bottom. [ustep]")
    raw_tiltdownlargefill = IntListValue([5, 650, 1000, 4, 1, 0, 64, 3], length=8, key="tiltdownlargefill", doc="Definitions for tilt down where printed area > limit4fast. Profiles, offsets and wait times.")
    raw_tiltdownsmallfill = IntListValue([5, 0, 0, 6, 1, 0, 0, 0], length=8, key="tiltdownsmallfill", doc="Definitions for tilt down where printed area < limit4fast. Profiles, offsets and wait times.")
    raw_tiltuplargefill = IntListValue([2, 400, 0, 5, 1, 0, 0, 0], length=8, key="tiltuplargefill", doc="Definitions for tilt up where printed area > limit4fast. Profiles, offsets and wait times.")
    raw_tiltupsmallfill = IntListValue([2, 400, 0, 5, 1, 0, 0, 0], length=8, key="tiltupsmallfill", doc="Definitions for tilt up where printed area < limit4fast. Profiles, offsets and wait times.")
    raw_tiltupsuperslow = IntListValue([7, 650, 1000, 4, 1, 0, 64, 3], length=8, key="tiltupsuperslow", doc="Definitions for tilt up where printed area < limit4fast. Profiles, offsets and wait times.")
    raw_tiltdownsuperslow = IntListValue([7, 400,    0, 5, 1, 0,  0, 0], length=8, key="tiltdownsuperslow ", doc="Definitions for tilt up when superslow movement profile is selected. Profiles, offsets and wait times.")
    limit4fast = IntValue(35, minimum=0, maximum=100, doc="Fast tearing is used if layer area is under this value. [%]")
    tiltFastTime = FloatValue(5.5, doc="Time necessary to perform fast tear off. [seconds]")
    tiltSlowTime = FloatValue(8.0, doc="Time necessary to perform slow tear off. [seconds]")
    tiltSuperSlowTime = FloatValue(14.0, doc="Time necessary to perform super slow tear off. [seconds]")

    superSlowTowerHopHeight_mm = FloatValue(5.0, doc="Minimal layerTowerHop enforced for the superSlow movement profile")

    @property
    def tuneTilt(self) -> List[List[int]]:
        return [self.raw_tiltdownlargefill, self.raw_tiltdownsmallfill, self.raw_tiltdownsuperslow, self.raw_tiltuplargefill, self.raw_tiltupsmallfill, self.raw_tiltupsuperslow]

    @tuneTilt.setter
    def tuneTilt(self, value: List[List[int]]):
        [self.raw_tiltdownlargefill, self.raw_tiltdownsmallfill, self.raw_tiltdownsuperslow, self.raw_tiltuplargefill, self.raw_tiltupsmallfill, self.raw_tiltupsuperslow] = value


    stirringMoves = IntValue(3, minimum=1, maximum=10, doc="Number of stirring moves")
    stirringDelay = IntValue(5, minimum=0, maximum=300)
    measuringMoves = IntValue(3, minimum=1, maximum=10)
    pwrLedPwm = IntValue(100, minimum=0, maximum=100, doc="Power LED brightness. [%]")
    MCBoardVersion = IntValue(6, minimum=5, maximum=6, doc="Motion controller board revision. Used to flash firmware.")
    towerSensitivity = IntValue(0, minimum=-2, maximum=2, factory=True, doc="Tower sensitivity adjustment")
    vatRevision = IntValue(0, minimum=0, maximum=1, doc="Resin vat revision: 0 = metalic (SL1); 1 = plastic (SL1S);")
    forceSlowTiltHeight = IntValue(1000000, minimum=0, maximum=10000000, doc="Force slow tilt after crossing limit4fast for defined height. [nm]")

    calibTowerOffset = IntValue(
        lambda self: self.calcMicroSteps(defines.defaultTowerOffset),
        doc="Adjustment of zero on the tower axis. [microsteps]",
    )

    # Exposure setup
    perPartes = BoolValue(False, doc="Expose areas larger than layerFill in two steps.")
    upAndDownUvOn = BoolValue(False)

    trigger = IntValue(
        0, minimum=0, maximum=20, doc="Duration of electronic trigger durint the layer change, currently discarded. [tenths of a second]"
    )
    layerTowerHop = IntValue(
        0, minimum=0, maximum=80000, doc="How much to rise the tower during layer change. [microsteps]"
    )
    delayBeforeExposure = IntValue(
        0, minimum=0, maximum=300, doc="Delay between tear off and exposure. [tenths of a second]"
    )
    delayAfterExposure = IntValue(
        0, minimum=0, maximum=300, doc="Delay between exposure and tear off. [tenths of a second]"
    )
    upAndDownWait = IntValue(10, minimum=0, maximum=600, doc="Up&Down wait time. [seconds]")
    upAndDownEveryLayer = IntValue(0, minimum=0, maximum=500, doc="Do Up&Down every N layers, 0 means never.")
    upAndDownZoffset = IntValue(0, minimum=-800, maximum=800)
    upAndDownExpoComp = IntValue(0, minimum=-10, maximum=300)

    # Fans & LEDs
    fan1Rpm = IntValue(
        2000, minimum=defines.fanMinRPM, maximum=defines.fanMaxRPM[0], factory=True, doc="UV LED fan RPMs."
    )
    fan2Rpm = IntValue(
        3300, minimum=defines.fanMinRPM, maximum=defines.fanMaxRPM[1], factory=True, doc="Blower fan RPMs."
    )
    fan3Rpm = IntValue(
        1000, minimum=defines.fanMinRPM, maximum=defines.fanMaxRPM[2], factory=True, doc="Rear fan RPMs."
    )
    fan1Enabled = BoolValue(True, doc="UV LED fan status.")
    fan2Enabled = BoolValue(True, doc="Blower fan status.")
    fan3Enabled = BoolValue(True, doc="Rear fan status.")
    uvCurrent = FloatValue(0.0, minimum=0.0, maximum=800.0, doc="UV LED current, DEPRECATED.")
    uvPwmTune = IntValue(0, minimum=-10, maximum=10, doc="Fine tune UV PWM. This value is added to standard uvPwm [-]")
    uvPwm = IntValue(
        lambda self: int(round(self.uvCurrent / 3.2)),
        minimum=0,
        maximum=250,
        factory=True,
        doc="UV LED PWM set by UV calibration (SL1) or calculated (SL1s) [-].",
    )

    @property
    def uvPwmPrint(self) -> int:
        """
        Final UV PWM used for printing

        :return: Value which is supposed to be used for printing
        """
        return self.uvPwm + self.uvPwmTune

    uvWarmUpTime = IntValue(120, minimum=0, maximum=300, doc="UV LED calibration warmup time. [seconds]")
    uvCalibIntensity = IntValue(140, minimum=90, maximum=200, doc="UV LED calibration intensity.")
    uvCalibMinIntEdge = IntValue(90, minimum=80, maximum=150, doc="UV LED calibration minimum intensity at the edge.")
    uvCalibBoostTolerance = IntValue(20, minimum=0, maximum=100, doc="Tolerance for allowing boosted results.")
    rpmControlUvLedMinTemp = IntValue(defines.minAmbientTemp, minimum=0, maximum=80, doc="At this temperature UV LED fan will spin at the minimum RPM.")
    rpmControlUvLedMaxTemp = IntValue(defines.maxUVTemp - 5, minimum=0, maximum=80, doc="At this temperature UV LED fan will spin at the maximum RPM.")
    rpmControlUvFanMinRpm = IntValue(defines.fanMinRPM, minimum=defines.fanMinRPM, maximum=defines.fanMaxRPM[0], doc="RPM is lineary mapped to UV LED temp. This is the lower limit..")
    rpmControlUvFanMaxRpm = IntValue(defines.fanMaxRPM[0], minimum=defines.fanMinRPM, maximum=defines.fanMaxRPM[0], doc="RPM is lineary mapped to UV LED temp. This is the upper limit.")
    rpmControlOverride = BoolValue(False, doc="Overide UV FAN RPM control with UV LED temp. Force the RPM set in this config.")
    tankCleaningExposureTime = IntValue(defines.tank_surface_cleaning_exposure_time_s, minimum=5, maximum=120, doc="Exposure time when running the tank surface cleaning wizard")
    tankCleaningGentlyUpProfile = IntValue(2, minimum=0, maximum=3, doc="Select the profile used for the upward movement of the platform in the tank surface cleaning wizard(should be cast into GentlyUpProfile enum).")
    tankCleaningMinDistance_nm = IntValue(0, minimum=0, maximum=5_000_000, doc="Distance of the garbage collector from the resin tank bottom when moving down.")
    currentProfilesSet = TextValue("n/a", doc="Last applied profiles set")

    raw_calibrated = BoolValue(False, key="calibrated")

    @property
    def calibrated(self) -> bool:
        """
        Printer calibration state

        The value can read as False when set to True as further requirements on calibration are checked in the getter.

        :return: True if printer is calibrated, False otherwise
        """
        # TODO: Throw away raw_calibrated, judge calibrated based on tilt/tower height
        return self.raw_calibrated and self.tiltHeight % 64 == 0

    @calibrated.setter
    def calibrated(self, value: bool) -> None:
        self.raw_calibrated = value

    towerHeight = IntValue(
        lambda self: self.calcMicroSteps(defines.defaultTowerHeight), doc="Maximum tower height. [microsteps]"
    )
    max_tower_height_mm = IntValue(150, key="maxTowerHeight_mm", doc="Maximum tower height in mm")
    showWizard = BoolValue(True, doc="Display wizard at startup if True.")
    showUnboxing = BoolValue(True, doc="Display unboxing wizard at startup if True.")
    showI18nSelect = BoolValue(True, doc="Display language select dialog at startup if True.")
    lockProfiles = BoolValue(False, doc="Restrict overwrite of SL1/SL1s profiles on startup.")
