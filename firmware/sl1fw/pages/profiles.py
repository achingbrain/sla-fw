# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

import os
import json
from copy import deepcopy

from sl1fw import defines
from sl1fw.libPages import page, Page


class ProfilesPage(Page):

    def __init__(self, display):
        super(ProfilesPage, self).__init__(display)
        self.pageUI = "setup"
        self.autorepeat = {
                "minus2g1" : (5, 1), "plus2g1" : (5, 1),
                "minus2g2" : (5, 1), "plus2g2" : (5, 1),
                "minus2g3" : (5, 1), "plus2g3" : (5, 1),
                "minus2g4" : (5, 1), "plus2g4" : (5, 1),
                "minus2g5" : (5, 1), "plus2g5" : (5, 1),
                "minus2g6" : (5, 1), "plus2g6" : (5, 1),
                "minus2g7" : (5, 1), "plus2g7" : (5, 1),
                }
        self.profilesNames = dict()
        self.profiles = None
        self.actualProfile = 0
        self.nameIndexes = set()
        self.profileItems = 7
        self.profilesFilename = "dummy.json"
    #enddef


    def show(self):
        self.items.update({
                "button1" : _("Export"),
                "button2" : _("Import"),
                "button4" : _("Save"),
                })
        super(ProfilesPage, self).show()
    #enddef


    def _value(self, index, valmin, valmax, change):
        if valmin <= self.profiles[self.actualProfile][index] + change <= valmax:
            self.profiles[self.actualProfile][index] += change
            if index in self.nameIndexes:
                self.showItems(**{ 'value2g%d' % (index + 1) : str(self.profilesNames[self.profiles[self.actualProfile][index]]) })
            else:
                self.showItems(**{ 'value2g%d' % (index + 1) : str(self.profiles[self.actualProfile][index]) })
            #endif
        else:
            self.display.hw.beepAlarm(1)
        #endif
    #enddef


    def _setProfile(self, profile = None):
        if profile is not None:
            self.actualProfile = profile
        #endif
        data = { "state1g1" : 0, "state1g2" : 0, "state1g3" : 0, "state1g4" : 0, "state1g5" : 0, "state1g6" : 0, "state1g7" : 0, "state1g8" : 0 }
        data["state1g%d" % (self.actualProfile + 1)] = 1

        for i in range(self.profileItems):
            if i in self.nameIndexes:
                data["value2g%d" % (i + 1)] = str(self.profilesNames[int(self.profiles[self.actualProfile][i])])
            else:
                data["value2g%d" % (i + 1)] = str(self.profiles[self.actualProfile][i])
            #endif
        #endfor

        self.showItems(**data)
    #enddef


    def button1ButtonRelease(self):
        ''' export '''
        savepath = self.getSavePath()
        if savepath is None:
            self.display.pages['error'].setParams(
                text=_("No USB storage present"))
            return "error"
        #endif

        profile_file = os.path.join(savepath, self.profilesFilename)

        try:
            with open(profile_file, "w") as f:
                f.write(json.dumps(self.profiles, sort_keys=True, indent=4, separators=(',', ': ')))
            #endwith
        except Exception:
            self.logger.exception("export exception:")
            self.display.pages['error'].setParams(
                text=_("Cannot export profile"))
            return "error"
        #endtry
    #enddef


    def button2ButtonRelease(self):
        ''' import '''
        savepath = self.getSavePath()
        if savepath is None:
            self.display.pages['error'].setParams(
                text=_("No USB storage present"))
            return "error"
        #endif

        profile_file = os.path.join(savepath, self.profilesFilename)

        if not os.path.isfile(profile_file):
            self.display.pages['error'].setParams(
                text=_("Cannot find profile to import"))
            return "error"
        #endif

        try:
            with open(profile_file, "r") as f:
                self.profiles = json.loads(f.read())
            #endwith
            self._setProfile()
            return
        except Exception:
            self.logger.exception("import exception:")
            self.display.pages['error'].setParams(
                text=_("Cannot import profile"))
            return "error"
        #endtry
    #enddef


    def button5ButtonRelease(self):
        ''' defaults '''
        try:
            with open(os.path.join(defines.dataPath, self.profilesFilename), "r") as f:
                self.profiles = json.loads(f.read())
            #endwith
            self._setProfile()
        except Exception:
            self.logger.exception("import exception:")
            self.display.pages['error'].setParams(
                text=_("Cannot load default profile"))
            return "error"
        #endtry
    #enddef


    def state1g1ButtonRelease(self):
        self._setProfile(0)
    #enddef


    def state1g2ButtonRelease(self):
        self._setProfile(1)
    #enddef


    def state1g3ButtonRelease(self):
        self._setProfile(2)
    #enddef


    def state1g4ButtonRelease(self):
        self._setProfile(3)
    #enddef


    def state1g5ButtonRelease(self):
        self._setProfile(4)
    #enddef


    def state1g6ButtonRelease(self):
        self._setProfile(5)
    #enddef


    def state1g7ButtonRelease(self):
        self._setProfile(6)
    #enddef


    def state1g8ButtonRelease(self):
        self._setProfile(7)
    #enddef


    def minus2g1Button(self):
        self._value(0, 0, 20000, -10)
    #enddef


    def plus2g1Button(self):
        self._value(0, 0, 20000, 10)
    #enddef


    def minus2g2Button(self):
        self._value(1, 0, 20000, -10)
    #enddef


    def plus2g2Button(self):
        self._value(1, 0, 20000, 10)
    #enddef


    def minus2g3Button(self):
        self._value(2, 0, 600, -1)
    #enddef


    def plus2g3Button(self):
        self._value(2, 0, 600, 1)
    #enddef


    def minus2g4Button(self):
        self._value(3, 0, 600, -1)
    #enddef


    def plus2g4Button(self):
        self._value(3, 0, 600, 1)
    #enddef


    def minus2g5Button(self):
        self._value(4, 0, 63, -1)
    #enddef


    def plus2g5Button(self):
        self._value(4, 0, 63, 1)
    #enddef


    def minus2g6Button(self):
        self._value(5, -128, 127, -1)
    #enddef


    def plus2g6Button(self):
        self._value(5, -128, 127, 1)
    #enddef


    def minus2g7Button(self):
        self._value(6, 0, 4000, -10)
    #enddef


    def plus2g7Button(self):
        self._value(6, 0, 4000, 10)
    #enddef

#endclass


@page
class PageTiltProfiles(ProfilesPage):
    Name = "tiltprofiles"

    def __init__(self, display):
        super(PageTiltProfiles, self).__init__(display)
        self.profilesFilename = "tilt_profiles.json"
        self.profilesNames = display.hw.getTiltProfilesNames()
        self.pageTitle = N_("Tilt Profiles")
    #enddef


    def show(self):
        self.items.update({
                "label1g1" : self.profilesNames[0],
                "label1g2" : self.profilesNames[1],
                "label1g3" : self.profilesNames[2],
                "label1g4" : self.profilesNames[3],
                "label1g5" : self.profilesNames[4],
                "label1g6" : self.profilesNames[5],
                "label1g7" : self.profilesNames[6],
                "label1g8" : self.profilesNames[7],

                "label2g1" : _("starting steprate"),
                "label2g2" : _("maximum steprate"),
                "label2g3" : _("acceleration"),
                "label2g4" : _("deceleration"),
                "label2g5" : _("current"),
                "label2g6" : _("stallguard threshold"),
                "label2g7" : _("coolstep threshold"),

                "button3" : _("Test"),
                "button5" : _("Defaults"),
                })
        super(PageTiltProfiles, self).show()
        if not self.profiles:
            self.profiles = self.display.hw.getTiltProfiles()
        #endif
        self._setProfile()
        self.display.pages['tiltmove'].changeProfiles(False)
    #enddef


    def button3ButtonRelease(self):
        ''' test '''
        self.display.hw.setTiltTempProfile(self.profiles[self.actualProfile])
        return "tiltmove"
    #endif


    def button4ButtonRelease(self):
        ''' save '''
        self.display.pages['tiltmove'].changeProfiles(True)
        self.display.hw.setTiltProfiles(self.profiles)
        self.profiles = None
        return super(PageTiltProfiles, self).backButtonRelease()
    #enddef


    def backButtonRelease(self):
        self.display.pages['tiltmove'].changeProfiles(True)
        self.profiles = None
        return super(PageTiltProfiles, self).backButtonRelease()
    #endif

#endclass


@page
class PageTowerProfiles(ProfilesPage):
    Name = "towerprofiles"

    def __init__(self, display):
        super(PageTowerProfiles, self).__init__(display)
        self.profilesFilename = "tower_profiles.json"
        self.profilesNames = display.hw.getTowerProfilesNames()
        self.pageTitle = N_("Tower Profiles")
    #enddef


    def show(self):
        self.items.update({
                "label1g1" : self.profilesNames[0],
                "label1g2" : self.profilesNames[1],
                "label1g3" : self.profilesNames[2],
                "label1g4" : self.profilesNames[3],
                "label1g5" : self.profilesNames[4],
                "label1g6" : self.profilesNames[5],
                "label1g7" : self.profilesNames[6],
                "label1g8" : self.profilesNames[7],

                "label2g1" : _("starting steprate"),
                "label2g2" : _("maximum steprate"),
                "label2g3" : _("acceleration"),
                "label2g4" : _("deceleration"),
                "label2g5" : _("current"),
                "label2g6" : _("stallguard threshold"),
                "label2g7" : _("coolstep threshold"),

                "button3" : _("Test"),
                "button5" : _("Defaults"),
                })
        super(PageTowerProfiles, self).show()
        if not self.profiles:
            self.profiles = self.display.hw.getTowerProfiles()
        #endif
        self._setProfile()
        self.display.pages['towermove'].changeProfiles(False)
    #enddef


    def button3ButtonRelease(self):
        ''' test '''
        self.display.hw.setTowerTempProfile(self.profiles[self.actualProfile])
        return "towermove"
    #enddef


    def button4ButtonRelease(self):
        ''' save '''
        self.display.pages['towermove'].changeProfiles(True)
        self.display.hw.setTowerProfiles(self.profiles)
        self.profiles = None
        return super(PageTowerProfiles, self).backButtonRelease()
    #enddef


    def backButtonRelease(self):
        self.display.pages['towermove'].changeProfiles(True)
        self.profiles = None
        return super(PageTowerProfiles, self).backButtonRelease()
    #enddef

#endclass


@page
class PageTuneTilt(ProfilesPage):
    Name = "tunetilt"

    def __init__(self, display):
        super(PageTuneTilt, self).__init__(display)
        self.profilesFilename = "tilt_tune_profiles.json"
        self.profilesNames = display.hw.getTiltProfilesNames()
        self.pageTitle = N_("Tilt Tune")
        self.nameIndexes = set((0,3))
        self.profileItems = 8
    #enddef


    def show(self):
        self.items.update({
                "label1g1" : _("Down slow"),
                "label1g2" : _("Down fast"),
                "label1g3" : _("Up"),

                "label2g1" : _("init profile"),
                "label2g2" : _("offset steps"),
                "label2g3" : _("offset delay [ms]"),
                "label2g4" : _("finish profile"),
                "label2g5" : _("tilt cycles"),
                "label2g6" : _("tilt delay [ms]"),
                "label2g7" : _("homing tolerance"),
                "label2g8" : _("homing cycles"),
                })
        super(PageTuneTilt, self).show()
        self.profiles = deepcopy(self.display.hwConfig.tuneTilt)
        self._setProfile()
    #enddef


    def button4ButtonRelease(self):
        ''' save '''
        self.display.hwConfig.update(
            tiltDownLargeFill = self.profiles[0],
            tiltDownSmallFill = self.profiles[1],
            tiltUp = self.profiles[2],
        )
        if not self.display.hwConfig.writeFile():
            self.display.pages['error'].setParams(
                text = _("Cannot save configuration"))
            return "error"
        #endif
        return super(PageTuneTilt, self).backButtonRelease()
    #enddef


    def backButtonRelease(self):
        self.display.pages['tiltmove'].changeProfiles(True)
        return super(PageTuneTilt, self).backButtonRelease()
    #endif


    def state1g4ButtonRelease(self):
        pass
    #enddef


    def state1g5ButtonRelease(self):
        pass
    #enddef


    def state1g6ButtonRelease(self):
        pass
    #enddef


    def state1g7ButtonRelease(self):
        pass
    #enddef


    def state1g8ButtonRelease(self):
        pass
    #enddef


    #init profile
    def minus2g1Button(self):
        self._value(0, 0, 7, -1)
    #enddef

    def plus2g1Button(self):
        self._value(0, 0, 7, 1)
    #enddef


    #offset steps
    def minus2g2Button(self):
        self._value(1, 0, 2000, -10)
    #enddef

    def plus2g2Button(self):
        self._value(1, 0, 2000, 10)
    #enddef


    #offset delay [ms]
    def minus2g3Button(self):
        self._value(2, 0, 4000, -10)
    #enddef

    def plus2g3Button(self):
        self._value(2, 0, 4000, 10)
    #enddef


    #finish profile
    def minus2g4Button(self):
        self._value(3, 0, 7, -1)
    #enddef

    def plus2g4Button(self):
        self._value(3, 0, 7, 1)
    #enddef


    #tilt cycles
    def minus2g5Button(self):
        self._value(4, 1, 10, -1)
    #enddef

    def plus2g5Button(self):
        self._value(4, 1, 10, 1)
    #enddef


    #tilt delay [ms]
    def minus2g6Button(self):
        self._value(5, 0, 4000, -10)
    #enddef

    def plus2g6Button(self):
        self._value(5, 0, 4000, 10)
    #enddef


    #homing tolerance
    def minus2g7Button(self):
        self._value(6, 0, 512, -1)
    #enddef

    def plus2g7Button(self):
        self._value(6, 0, 512, 1)
    #enddef


    #homing cycles
    def minus2g8Button(self):
        self._value(7, 1, 10, -1)
    #enddef

    def plus2g8Button(self):
        self._value(7, 1, 10, 1)
    #enddef

#endclass
