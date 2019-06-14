# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import os
import logging
import zipfile
import json
import toml

from sl1fw import defines


class MyBool:

    def __init__(self, value):
        self.value = value
    #enddef

    def __bool__(self):
        return self.value
    #enddef

    def __str__(self):
        return "on" if self.value else "off"
    #endef

    def __int__(self):
        return int(self.value)
    #endef

    def __eq__(self, other):
        if isinstance(other, MyBool):
            return self.value == other.value
        else:
            return False
        #endif
    #enddef

    def inverse(self):
        self.value = not self.value
    #enddef

    __nonzero__=__bool__
#endclass


class FileConfig(object):

    def __init__(self, name, configFile, defaults = {}):
        self._logger = logging.getLogger(name)
        self._defaults = defaults
        self.parseFile(configFile)
    #enddef

    def _readFile(self, configFile):
        self._data = dict()
        self._lines = list()
        self._configFile = configFile
        if configFile is not None and os.path.exists(configFile):
            with open(configFile) as f:
                for line in f:
                    self._parseLine(line)
                #endfor
            #endwith
        #endif
    #enddef

    def _readText(self, configText):
        self._data = dict()
        self._lines = list()
        for line in configText.splitlines():
            self._parseLine(line)
        #endfor
    #enddef

    def _parseLine(self, line):
        eq_index = line.find('=')
        if eq_index > 0:
            var_name = line[:eq_index].strip()
            value = line[eq_index + 1:].strip()
            self._data[var_name.lower()] = value
            self._lines.append((var_name, value))
        else:
            self._lines.append((None, line.strip()))
        #endif
    #enddef

    # for pylint only :)
    def _parseData(self):
        self._logger.error("THIS SHOULD BE OVERRIDDEN!")
    #enddef

    def parseFile(self, configFile):
        self._readFile(configFile)
        self._parseData()
    #enddef

    def parseText(self, configText):
        self._readText(configText)
        self._parseData()
    #enddef

    def writeFile(self, filename = None):
        try:
            if filename is None:
                filename = self._configFile
            else:
                self._configFile = filename
            #endif
            writename = filename + ".tmp"
            with open(writename, "w") as f:
                f.write(self.getSourceString())
            #endwith
            os.rename(writename, filename)
        except Exception:
            self._logger.exception("writeFile() exception:")
            return False
        #endtry

        return True
    #enddef

    def update(self, **kwargs):
        '''
        Update values in the config

        Changes are not propagated to the underlying file. Use 'writeFile' to sync changes.

        :param kwargs: Dictionary with key=value pairs to update. Object members
        cannot be used directly !!! Setting value to None removes key from the configuration.
        '''

        lowerkeys = dict()
        for key,val in kwargs.items():
            lowerkey = key.lower()
            if val is None:
                self._data[lowerkey] = None
            elif isinstance(val, list):
                self._data[lowerkey] = " ".join(map(lambda x: str(x), val))
            else:
                self._data[lowerkey] = str(val)
            #endif
            self._logger.debug("update: %s = %s", lowerkey, self._data[lowerkey])
            lowerkeys[lowerkey] = key
        #endfor
        newLines = list()
        for key,val in self._lines:
            if key is None:
                newLines.append((None, val))
            else:
                lowerkey = key.lower()
                if lowerkey not in lowerkeys or kwargs[lowerkeys[lowerkey]] is not None:
                    newLines.append((key, self._data[lowerkey]))
                #endif
                if lowerkey in lowerkeys:
                    del kwargs[lowerkeys[lowerkey]]
                #endif
            #endif
        #endfor
        for key,val in kwargs.items():
            if val is not None:
                newLines.append((key, val))
            #endif
        #endfor
        self._lines = newLines
        self._parseData()
    #enddef

    def getSourceString(self):
        return "\r\n".join(self._getSourceLines())
    #enddef

    def getDict(self):
        out = {}
        for key, val in vars(self).items():
            if not key.startswith("_"):
                out[key] = val
            #endif
        #endfor
        return out
    #enddef

    def getJson(self):
        return json.dumps(self.getDict())
    #enddef

    def logAllItems(self):
        items = vars(self)
        for key in sorted(items):
            if not key.startswith("_"):
                self._logger.info("AllItems: %s = %s" % (key, items[key]))
            #endif
        #endfor
    #enddef

    def defaultsSet(self):
        return self._defaults
    #enddef

    def __str__(self):
        rows = list(("",))
        items = vars(self)
        for key in sorted(items):
            if not key.startswith("_"):
                rows.append("%s = %s" % (key, items[key]))
            #endif
        #endfor
        return "\n".join(rows)
    #enddef

    def logFile(self):
        for line in self._getSourceLines():
            self._logger.info("File: %s" % line)
        #endfor
    #enddef

    def _getSourceLines(self):
        retval = list()
        for key,val in self._lines:
            if key is None:
                retval.append(val)
            else:
                retval.append("%s = %s" % (key, val))
            #endif
        #endfor
        return retval
    #enddef

    def _parseInt(self, key, default = -1):
        if key in self._defaults:
            default = self._defaults[key]
        #endif

        try:
            ret = int(self._data.get(key, default))
            return ret
        except Exception:
            return default
        #endtry
    #enddef

    def _parseIntMinMax(self, key, default, minval, maxval):
        val = self._parseInt(key, default);
        if val > maxval:
            val = maxval
        elif val < minval:
            val = minval
        #endif
        return val
    #enddef

    def _parseIntList(self, key, count = None, default = list()):
        try:
            ret = list(map(lambda x: int(x), self._data.get(key, "").split()))
            if count and len(ret) != count:
                return default
            #endif
            return ret
        except Exception:
            return default
        #endtry
    #enddef

    def _parseFloat(self, key, default = -1.0, exact = False):
        if key in self._defaults:
            default = self._defaults[key]
        #endif

        try:
            val = float(self._data.get(key, default))
            if exact:
                return val
            else:
                return round(val, 3)
            #endif
        except Exception:
            return default
        #endtry
    #enddef

    def _parseFloatMinMax(self, key, default, minval, maxval):
        val = self._parseFloat(key, default);
        if val > maxval:
            val = maxval
        elif val < minval:
            val = minval
        #endif
        return val
    #enddef

    def _parseFloatList(self, key, count = 0, default = list()):
        try:
            ret = list(map(lambda x: float(x), self._data.get(key, "").split()))
            if count and len(ret) != count:
                return default
            #endif
            return ret
        except Exception:
            return default
        #endtry
    #enddef

    def _parseBool(self, key, default = False):
        if key in self._defaults:
            default = self._defaults[key]
        #endif

        try:
            val = self._data.get(key, "").lower()
            if val == "on" or val == "yes":
                return MyBool(True)
            elif val == "off" or val == "no":
                return MyBool(False)
            else:
                return MyBool(int(val) != 0 if val != "" else default)
            #endif
        except Exception:
            self._logger.exception("_parseBool() exception:")
            return default
        #endtry
    #enddef

    def _parseString(self, key, default = ""):
        if key in self._defaults:
            default = self._defaults[key]
        #endif

        try:
            return self._data.get(key, default).strip('"')
        except Exception:
            return default
        #endtry
    #enddef

#endclass


class HwConfig(FileConfig):

    def __init__(self, configFile = None, defaults = {}):
        super(HwConfig, self).__init__("HwConfig", configFile, defaults)
        self.os = OsConfig()
        self.factoryMode = False

        # Load factory mode configuration
        try:
            with open(defines.factoryConfigFile, "r") as f:
                if toml.load(f)['factoryMode']:
                    self.factoryMode = True
                #endif
            #endwith
        except:
            self._logger.exception("Failed to load factory configuration, keeping disabled")
        #endtry
    #enddef

    def _parseData(self):
        # Hardware setup
        self.fanCheck = self._parseBool("fancheck", True)
        self.coverCheck = self._parseBool("covercheck", True)
        self.MCversionCheck = self._parseBool("mcversioncheck", True)
        self.resinSensor = self._parseBool("resinsensor", True)
        self.autoOff = self._parseBool("autooff", True)
        self.mute = self._parseBool("mute", False)

        self.screwMm = self._parseInt("screwmm", 4)
        self.microStepsMM = 200 * 16 / self.screwMm
        self.tiltHeight = self._parseInt("tiltheight", defines.defaultTiltHeight) #safe value
        self.stirringMoves = self._parseIntMinMax("stirringmoves", 3, 1, 10)
        self.stirringDelay = self._parseIntMinMax("stirringdelay", 5, 0, 300)
        self.measuringMoves = self._parseIntMinMax("measuringmoves", 3, 1, 10)
        self.pwrLedPwm = self._parseIntMinMax("pwrledpwm", 100, 0, 100)

        self.MCBoardVersion = self._parseIntMinMax("mcboardversion", 6, 5, 6)

        # Advanced settings
        self.tiltSensitivity = self._parseInt("tiltsensitivity", 0)
        self.towerSensitivity = self._parseInt("towersensitivity", 0)
        self.limit4fast = self._parseIntMinMax("limit4fast", 45, 0, 100)
        self.whitePixelsThd = (1440 * 2560) * (self.limit4fast / 100.0)
        self.calibTowerOffset = self._parseInt("calibtoweroffset", self.calcMicroSteps(defines.defaultTowerOffset))

        # Exposure setup
        self.blinkExposure = self._parseBool("blinkexposure", True)
        self.perPartes = self._parseBool("perpartesexposure", False)
        self.tilt = self._parseBool("tilt", True)

        self.trigger = self._parseIntMinMax("trigger", 0, 0, 20)
        self.layerTowerHop = self._parseIntMinMax("layertowerhop", 0, 0, 8000)
        self.delayBeforeExposure = self._parseIntMinMax("delaybeforeexposure", 0, 0, 300)
        self.delayAfterExposure = self._parseIntMinMax("delayafterexposure", 0, 0, 300)
        self.upAndDownWait = self._parseIntMinMax("upanddownwait", 10, 0, 600)
        self.upAndDownEveryLayer = self._parseIntMinMax("upanddowneverylayer", 0, 0, 500)

        # Fans & LEDs
        self.fan1Pwm = self._parseIntMinMax("fan1pwm", 60, 0, 100)
        self.fan2Pwm = self._parseIntMinMax("fan2pwm", 100, 0, 100)
        self.fan3Pwm = self._parseIntMinMax("fan3pwm", 40, 0, 100)
        uvCurrent = self._parseFloatMinMax("uvcurrent", 700.8, 0.0, 800.0)
        self.uvPwm = self._parseIntMinMax("uvpwm", int(round(uvCurrent / 3.2)), 0, 250)
        self.uvCalibTemp = self._parseIntMinMax("uvcalibtemp", 40, 30, 50)
        self.uvCalibIntensity = self._parseIntMinMax("uvcalibintensity", 140, 80, 200)

        # Tilt & Tower -> Tilt tune
        self.tuneTilt = list()
        self.tuneTilt.append(self._parseIntList("tiltdownlargefill", [5, 650, 1000, 4, 1, 0, 64, 3]))
        self.tuneTilt.append(self._parseIntList("tiltdownsmallfill", [5, 0, 0, 6, 1, 0, 0, 0]))
        self.tuneTilt.append(self._parseIntList("tiltup", [2, 400, 0, 5, 1, 0, 0, 0]))
        #hotfix. TODO remove
        if len(self.tuneTilt[0]) != 8 or len(self.tuneTilt[1]) != 8 or len(self.tuneTilt[2]) != 8:
            self.tuneTilt[0] = [5, 650, 1000, 4, 1, 0, 64, 3]
            self.tuneTilt[1] = [5, 0, 0, 6, 1, 0, 0, 0]
            self.tuneTilt[2] = [2, 400, 0, 5, 1, 0, 0, 0]
        #endif

        # not adjustable in admin
        self.pixelSize = self._parseFloat("pixelsize", 0.046875, True)    # 5.5" LCD
        self.calibrated = self._parseBool("calibrated", False)
        self.towerHeight = self._parseInt("towerheight", self.calcMicroSteps(defines.defaultTowerHeight)) # safe value
        self.tiltFastTime = self._parseFloat("tiltfasttime", 5.5)
        self.tiltSlowTime = self._parseFloat("tiltslowtime", 8.0)
        self.showWizard = self._parseBool("showwizard", True)
        self.showUnboxing = self._parseBool("showunboxing", True)
    #enddef

    def calcMicroSteps(self, mm):
        return int(mm * self.microStepsMM)
    #enddef

    def calcMM(self, microSteps):
        return round(float(microSteps) / self.microStepsMM, 3)
    #enddef

#endclass


class OsConfig(FileConfig):

    def __init__(self, configFile = "/etc/os-release"):
        super(OsConfig, self).__init__("OsConfig", configFile)
    #enddef

    def _parseData(self):
        self.id = self._parseString("id")
        self.name = self._parseString("name", _("unknown"))
        self.version = self._parseString("version", _("unknown"))
        self.versionId = self._parseString("version_id", _("unknown"))
    #enddef

#endclass


class WizardData(FileConfig):

    def __init__(self, configFile = None):
        super(WizardData, self).__init__("WizardData", configFile)
    #enddef

    def _parseData(self):
        # following values are for quality monitoring systems
        self.osVersion = self._parseString("osversion")
        self.sl1fwVersion = self._parseString("sl1fwversion")
        self.a64SerialNo = self._parseString("a64serialno")
        self.mcSerialNo = self._parseString("mcserialno")
        self.mcFwVersion = self._parseString("mcfwversion")
        self.mcBoardRev = self._parseString("mcboardrev")
        self.towerHeight = self._parseInt("towerheight")
        self.tiltHeight = self._parseInt("tiltheight")
        uvCurrent = self._parseFloat("uvcurrent")
        self.uvPwm = self._parseInt("uvpwm", int(round(uvCurrent / 3.2)))

        # following values are measured and saved in initial wizard
        # data in mV for 1/6, 1/2, 1/1 of max PWM for MC board
        self.wizardUvVoltageRow1 = self._parseIntList("wizarduvvoltagerow1")
        # data in mV for 1/6, 1/2, 1/1 of max PWM for MC board
        self.wizardUvVoltageRow2 = self._parseIntList("wizarduvvoltagerow2")
        # data in mV for 1/6, 1/2, 1/1 of max PWM for MC board
        self.wizardUvVoltageRow3 = self._parseIntList("wizarduvvoltagerow3")
        # fans RPM when using default PWM
        self.wizardFanRpm = self._parseIntList("wizardfanrpm")
        # UV LED temperature at the beginning of test (should be close to ambient)
        self.wizardTempUvInit = self._parseFloat("wizardtempuvinit")
        # UV LED temperature after warmup test
        self.wizardTempUvWarm = self._parseFloat("wizardtempuvwarm")
        # ambient sensor temperature
        self.wizardTempAmbient = self._parseFloat("wizardtempambient")
        # A64 temperature
        self.wizardTempA64 = self._parseFloat("wizardtempa64")
        # measured fake resin volume in wizard (without resin with rotated platform)
        self.wizardResinVolume = self._parseInt("wizardresinvolume")

        # following values are measured and saved in automatic UV LED calibration
        self.uvSensorData = self._parseIntList("uvsensordata")
        self.uvTemperature = self._parseFloat("uvtemperature", -273.2)
        self.uvDateTime = self._parseString("uvdatetime", "_NOT_SET_")
        self.uvMean = self._parseFloat("uvmean")
        self.uvStdDev = self._parseFloat("uvstddev")
        self.uvMinValue = self._parseInt("uvminvalue")
        self.uvMaxValue = self._parseInt("uvmaxvalue")
        self.uvPercDiff = self._parseFloatList("uvpercdiff")
        uvFoundCurrent = self._parseFloat("uvfoundcurrent")
        self.uvFoundPwm = self._parseInt("uvfoundpwm", int(round(uvFoundCurrent / 3.2)))
    #enddef

#endclass


class PrintConfig(FileConfig):

    def __init__(self, hwConfig, configFile = None):
        self._hwConfig = hwConfig
        self.zipName = None
        self.modificationTime = None
        super(PrintConfig, self).__init__("PrintConfig", configFile)
    #enddef

    def writeFile(self, filename = None):
        # FIXME poresit i pro ini v zipu!
        raise Exception("Not implemented!")
    #enddef

    def parseFile(self, zipName):
        self._data = dict()
        self._lines = list()

        # for defaults
        if zipName is None:
            self._parseData()
            return
        #endif

        self._logger.debug("Opening project file '%s'", zipName)

        if not os.path.isfile(zipName):
            self._logger.exception("Project lookup exception: file not exists: " + zipName)
            self.zipError = _("Project file not found.")
            return
        #endif

        self.toPrint = []
        self.zipError = _("Can't read project data.")

        # TODO: Get project completition time from config file once it is available
        # TODO: modificationTime is not read from config. Thus it does not belong here.
        try:
            self.modificationTime = os.path.getmtime(zipName)
        except Exception as e:
            self._logger.exception("Cannot get project modification time:" + str(e))
        #endtry

        try:
            zf = zipfile.ZipFile(zipName, 'r')
            self.parseText(zf.read(defines.configFile).decode('utf-8'))
            namelist = zf.namelist()
            zf.close()
        except Exception as e:
            self._logger.exception("zip read exception:" + str(e))
            return
        #endtry

        # Set paths
        dirName = os.path.dirname(zipName)
        self._configFile = os.path.join(dirName, "FAKE_" + defines.configFile)
        self.zipName = zipName

        for filename in namelist:
            fName, fExt = os.path.splitext(filename)
            if fExt.lower() == ".png" and fName.startswith(self.projectName):
                self.toPrint.append(filename)
            #endif
        #endfor

        self.toPrint.sort()
        self.totalLayers = len(self.toPrint)

        self._logger.debug("found %d layers", self.totalLayers)
        if self.totalLayers < 2:
            self.zipError = _("Not enough layers.")
        else:
            self.zipError = None
        #endif
    #enddef

    def _parseData(self):
        self.projectName = self._parseString("jobdir", "no project")

        self.expTime = self._parseFloat("exptime", 8.0)
        self.expTime2 = self._parseFloat("exptime2", self.expTime)
        self.expTime3 = self._parseFloat("exptime3", self.expTime)
        self.expTimeFirst = self._parseFloat("exptimefirst", 35.0)

        layerHeight = self._parseFloat("layerheight")
        if layerHeight > 0.0099:
            self.layerMicroSteps = self._hwConfig.calcMicroSteps(layerHeight)
            self.layerMicroSteps2 = self._hwConfig.calcMicroSteps(self._parseFloat("layerheight2", layerHeight))
            self.layerMicroSteps3 = self._hwConfig.calcMicroSteps(self._parseFloat("layerheight3", layerHeight))
        else:
            # historicky zmatlano aby sedelo ze pri 8 mm na otacku stepNum = 40 odpovida 0.05 mm
            self.layerMicroSteps = self._parseInt("stepnum", 40) / (self._hwConfig.screwMm / 4)
            self.layerMicroSteps2 = self._parseInt("stepnum2", self.layerMicroSteps)
            self.layerMicroSteps3 = self._parseInt("stepnum3", self.layerMicroSteps)
        #endif
        layerHeightFirst = self._parseFloat("layerheightfirst", 0.05)
        self.layerMicroStepsFirst = self._hwConfig.calcMicroSteps(layerHeightFirst)

        self.slice2 = self._parseInt("slice2", 9999998) # vrstva prechodu na parametry2
        self.slice3 = self._parseInt("slice3", 9999999) # vrstva prechodu na parametry3
        self.fadeLayers = self._parseIntMinMax("numfade", 10, 3, 200)

        self.calibrateTime = self._parseFloat("calibratetime", self.expTime)
        self.calibrateRegions = self._parseInt("calibrateregions", 0)
        self.calibrateInfoLayers = self._parseInt("calibrateinfolayers", 10)
        self.calibratePenetration = int(self._parseFloat("calibratepenetration", 0.5) / self._hwConfig.pixelSize)

        self.usedMaterial = self._parseFloat("usedmaterial", defines.resinMaxVolume - defines.resinMinVolume)
        self.layersSlow = self._parseInt("numslow", 0)
        self.layersFast = self._parseInt("numfast", 0)

        self.totalLayers = self.layersSlow + self.layersFast
        self.zipError = _("No data was read.")
    #enddef

#endclass


class ConfigHelper(object):
    """ This class provides a wrapper around config that behaves in a bit more sane way than the original config. Values
    can be read AND set using cameCase attribute access. Changes are saved to underlying config and configuration file
    upon a commit operation. Dirty values can be detected using a 'changed' method."""

    def __init__(self, config):
        self._config = config
        self._changed = {}
    #enddef


    def __getattr__(self, item):
        if item.lower() in self._changed:
            value = self._changed[item.lower()]
        else:
            value = getattr(self._config, item)
        #endif

        if isinstance(value, MyBool):
            value = bool(value)
        #endif

        return value
    #enddef


    def __setattr__(self, key, value):
        if key.startswith('_'):
            object.__setattr__(self, key, value)
        else:
            # Determine new value, MyBool in underlying config requires special handling
            if isinstance(getattr(self._config, key), MyBool):
                change = MyBool(value)
            else:
                change = value
            #endif

            # Update changed or reset it if change is returning to original value
            if change == getattr(self._config, key):
                if key.lower() in self._changed:
                    del self._changed[key.lower()]
                #endif
            else:
                self._changed[key.lower()] = change
            #endif
        #endif
    #enddef


    def commit(self):
        """
        Save changes to underlying config and write it to file

        :return: Config file write operation result. True is successful, false otherwise.
        """
        for key, value in self._changed.items():
            self._config.update(**{key: str(value)})
        #endfor
        self._changed = {}
        return self._config.writeFile()
    #enddef


    def changed(self, key = None):
        """
        Test for changes relative to underlying config.

        :param key: Test only for specific key. If not specified or None changes on all keys are checked.
        :return: True if changed, false otherwise
        """
        if key is None:
            return bool(self._changed)
        else:
            return key.lower() in self._changed
    #enddef

#endclass
