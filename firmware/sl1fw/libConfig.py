# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018 Prusa Research s.r.o. - www.prusa3d.com

import os
import logging
import hashlib
import zipfile

import defines

class MyBool:

    def __init__(self, value):
        self.value = value
    #enddef

    def __bool__(self):
        return self.value
    #enddef

    def __str__(self):
        return "yes" if self.value else "no"
    #endef

    __nonzero__=__bool__
#endclass


class FileConfig(object):

    def __init__(self, configFile):
        self._logger = logging.getLogger(self._name)
        self.parseFile(configFile)
    #enddef

    def _readFile(self, configFile):
        self._data = dict()
        self._lines = list()
        self.configFound = False
        self.configFile = configFile
        if configFile is not None and os.path.exists(configFile):
            self.configFound = True
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
                filename = self.configFile
            else:
                self.configFile = filename
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

    # keys in kwargs must be lowercased file keywords not object members!!!
    # values must be strings!!!
    def update(self, **kwargs):
        for key,val in kwargs.iteritems():
            self._logger.debug("update: %s = %s", key, str(val))
            self._data[key.lower()] = val
        #endfor
        newLines = list()
        for key,val in self._lines:
            if key is None:
                newLines.append((None, val))
            else:
                lowerkey = key.lower()
                newLines.append((key, self._data[lowerkey]))
                if lowerkey in kwargs:
                    del kwargs[lowerkey]
                #endif
            #endif
        #endfor
        for key,val in kwargs.iteritems():
            newLines.append((None, ""))
            newLines.append((key, val))
        #endfor
        self._lines = newLines
        self._parseData()
    #enddef

    def getSourceString(self):
        return "\r\n".join(self._getSourceLines())
    #enddef

    def logAllItems(self):
        items = vars(self)
        for key in sorted(items):
            if not key.startswith("_"):
                self._logger.info("AllItems: %s = %s" % (key, items[key]))
            #endif
        #endfor
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

    def getHash(self):
        h = hashlib.md5()
        for key,val in self._lines:
            if key is not None:
                h.update(key)
            #endif
            h.update(val)
        #endfor

        self._logger.debug("hash: %s", h.hexdigest())
        return h.digest()
    #enddef

    def _parseInt(self, key, default = -1):
        try:
            return int(self._data.get(key, default))
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

    def _parseFloat(self, key, default = -1.0, exact = False):
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

    def _parseBool(self, key, default = False):
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
            return MyBool(default)
        #endtry
    #enddef

    def _parseString(self, key, default = ""):
        try:
            return self._data.get(key, default).strip('"')
        except Exception:
            return default
        #endtry
    #enddef

#endclass


class HwConfig(FileConfig):

    def __init__(self, configFile = None):
        self._name = "HwConfig"
        super(HwConfig, self).__init__(configFile)
        self.os = OsConfig()
    #enddef

    def _parseData(self):
        self.fanCheck = self._parseBool("fancheck", False)
        self.coverCheck = self._parseBool("covercheck", False)
        self.MCversionCheck = self._parseBool("mcversioncheck", True)
        self.screwMm = self._parseInt("screwmm", 4)
        self.microStepsMM = 200 * 16 / self.screwMm
        self.pixelSize = self._parseFloat("pixelsize", 0.046875, True)    # 5.5" LCD

        self.calibrated = self._parseBool("calibrated", False)
        self.towerHeight = self._parseInt("towerheight", self.calcMicroSteps(128)) # safe value
        self.tiltHeight = self._parseInt("tiltheight", 1600) # 100 steps 16 microsteps each
        self.tiltInitSteps = self._parseInt("tiltinitsteps", 50)
        self.tiltBreakSteps = self._parseInt("tiltbreaksteps", 500)
        self.tiltReturnSlowSteps = self._parseInt("tiltreturnslowsteps", 100)
        self.resinSensor = self._parseBool("resinsensor", False)
        self.logTiltLoad = self._parseBool("logtiltload", False)
        self.warmUp = self._parseInt("warmup", 0)
        self.blinkExposure = self._parseBool("blinkexposure", False)

        self.fan1Pwm = self._parseIntMinMax("fan1pwm", 100, 0, 100)
        self.fan2Pwm = self._parseIntMinMax("fan2pwm", 100, 0, 100)
        self.fan3Pwm = self._parseIntMinMax("fan3pwm", 100, 0, 100)
        self.uvCurrent = self._parseFloatMinMax("uvcurrent", 700.8, 0.0, 800.0)
        self.pwrLedPwm = self._parseIntMinMax("pwrledpwm", 100, 0, 100)
        self.trigger = self._parseIntMinMax("trigger", 0, 0, 20)
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
        self._name = "OsConfig"
        super(OsConfig, self).__init__(configFile)
    #enddef

    def _parseData(self):
        self.id = self._parseString("id")
        self.name = self._parseString("name", "unknown")
        self.version = self._parseString("version", "unknown")
        self.versionId = self._parseString("version_id", "unknown")
    #enddef

#endclass


class FwConfig(FileConfig):

    def __init__(self, configFile = None):
        self._name = "FwConfig"
        super(FwConfig, self).__init__(configFile)
    #enddef

    def _parseData(self):
        self.version = self._parseString("swversion")
    #enddef

#endclass


class NetConfig(FileConfig):

    def __init__(self, configFile = None):
        self._name = "NetConfig"
        super(NetConfig, self).__init__(configFile)
    #enddef

    def _parseData(self):
        self.image = self._parseString("image")
        self.firmware = self._parseString("firmware")
    #enddef

#endclass


class PrintConfig(FileConfig):

    def __init__(self, hwConfig, configFile = None):
        self._name = "PrintConfig"
        self._hwConfig = hwConfig
        self.final = False
        super(PrintConfig, self).__init__(configFile)
    #enddef

    def writeFile(self, filename = None):
        # FIXME poresit i pro ini v zipu!
        raise Exception("Not implemented!")
    #enddef

    def parseFile(self, configFile):
        super(PrintConfig, self).parseFile(configFile)

        self.zipName = None
        self.loadSrc = "USB"

        if configFile is not None:
            if not self.configFound:
                # kdyz nemame config.ini, zkusime jeste novy format projektu
                try:
                    dirName = os.path.dirname(configFile)
                    self._logger.debug("Looking for DWZ files in '%s'", dirName)
                    for infile in [ f for f in os.listdir(dirName) if os.path.isfile(os.path.join(dirName, f)) ]:
                        fName, fExt = os.path.splitext(infile)
                        if fExt.lower() == ".dwz":
                            projFullName = os.path.join(dirName, infile)
                            projFile = zipfile.ZipFile(projFullName)
                            self.parseText(projFile.read(defines.configFile))
                            if len(self.action):
                                self._logger.debug("Found DWZ file '%s'", projFullName)
                                self.zipName = projFullName
                                self.configFile = os.path.join(dirName, "FAKE_" + defines.configFile)
                                self.configFound = True
                                if dirName == defines.ramdiskPath:
                                    # soubor je v ramdisku -> nahrano po LAN
                                    self.loadSrc = "LAN"
                                #endif
                                break
                            #endif
                        #endif
                    #endfor
                except OSError:
                    pass
                except Exception as e:
                    self._logger.exception("DWZ lookup exception:")
                #endtry
            else:
                # nalezeni zip souboru pro variantu s externim config.ini
                dirName = os.path.dirname(self.configFile)
                # config na USB, ale ne v jeho rootu
                zipDir = dirName
                if dirName == defines.ramdiskPath:
                    # config je v ramdisku -> nahrano po LAN
                    self.loadSrc = "LAN"
                elif dirName == defines.usbPath:
                    # config v rootu USB, nutno pridat projectName
                    zipDir = os.path.join(dirName, self.projectName)
                #endif

                self._logger.debug("Looking for ZIP files in '%s'", zipDir)
                try:
                    for infile in [ f for f in os.listdir(zipDir) if os.path.isfile(os.path.join(zipDir, f)) ]:
                        fName, fExt = os.path.splitext(infile)
                        if fExt.lower() == ".zip" and fName == self.projectName:
                            self.zipName = os.path.join(zipDir, infile)
                            self._logger.debug("Found ZIP file '%s'", self.zipName)
                            break
                        #endif
                    #endfor
                except OSError:
                    pass
                except Exception as e:
                    self._logger.exception("ZIP lookup exception:")
                #endtry

            #endif
            self.readZipFile()
        #endif
    #enddef

    def readZipFile(self):
        self.totalLayers = 0
        self.toPrint = []
        self.zipError = "Can't read project data."

        if self.zipName is None:
            self._logger.error("ZIP file not found")
            return
        #endif

        try:
            zf = zipfile.ZipFile(self.zipName, 'r')
            namelist = zf.namelist()
            zf.close()
        except Exception as e:
            self._logger.exception("zip read exception:")
            return
        #endif

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
            self.zipError = "Not enough layers."
        else:
            self.zipError = None
        #endif
    #enddef

    def _parseData(self):
        self.action = self._parseString("action")
        self.projectName = self._parseString("jobdir", "no project")
        self.direct = self._parseBool("direct", False)
        self.autoOff = self._parseBool("autooff", True)

        self.expTime = self._parseFloat("exptime", 8.0)
        self.expTime2 = self._parseFloat("exptime2", self.expTime)
        self.expTime3 = self._parseFloat("exptime3", self.expTime)
        self.expTimeFirst = self._parseFloat("exptimefirst", 35.0)

        self.calibrateTime = self._parseFloat("calibratetime", self.expTime)
        self.calibrateRegions = self._parseInt("calibrateregions", 0)
        self.calibrateInfoLayers = self._parseInt("calibrateinfolayers", 10)

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

        self.slice2 = self._parseInt("slice2", 9999998) # vrstva prechodu na parametry2
        self.slice3 = self._parseInt("slice3", 9999999) # vrstva prechodu na parametry3
        self.fadeLayers = self._parseIntMinMax("numfade", 10, 3, 200)

        self.tiltDelayBefore = self._parseFloat("tiltdelaybefore", 0.0)
        self.tiltDelayAfter = self._parseFloat("tiltdelayafter", 0.0)
        self.upAndDownWait = self._parseInt("upanddownwait", 10)
        self.upAndDownEveryLayer = self._parseInt("upanddowneverylayer", 0)
        self.tilt = self._parseBool("tilt", True)
        self.fakeTiltUp = self._hwConfig.calcMicroSteps(self._parseInt("faketiltup", 5))
    #enddef

#endclass
