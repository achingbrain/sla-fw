# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
from sl1fw.libConfig import ConfigException
from sl1fw.pages import page
from sl1fw.libPages import Page


class MovePage(Page):

    # for pylint only :)
    def _up(self, dummy):
        self.logger.error("THIS SHOULD BE OVERRIDDEN!")
    #enddef


    # for pylint only :)
    def _down(self, dummy):
        self.logger.error("THIS SHOULD BE OVERRIDDEN!")
    #enddef


    # for pylint only :)
    def _stop(self):
        self.logger.error("THIS SHOULD BE OVERRIDDEN!")
    #enddef


    def upfastButton(self):
        self._up(False)
    #enddef


    def upfastButtonRelease(self):
        self._stop()
    #enddef


    def upslowButton(self):
        self._up(True)
    #enddef


    def upslowButtonRelease(self):
        self._stop()
    #enddef


    def downfastButton(self):
        self._down(False)
    #enddef


    def downfastButtonRelease(self):
        self._stop()
    #enddef


    def downslowButton(self):
        self._down(True)
    #enddef


    def downslowButtonRelease(self):
        self._stop()
    #enddef

#endclass


@page
class PageTowerMove(MovePage):
    Name = "towermove"

    def __init__(self, display):
        super(PageTowerMove, self).__init__(display)
        self.pageUI = "towermove"
        self.pageTitle = N_("Tower Move")
        self.autorepeat = { "upfast" : (1, 1), "upslow" : (1, 1), "downfast" : (1, 1), "downslow" : (1, 1) }
        self.setProfiles = True
    #enddef


    def show(self):
        self.items["value"] = self.display.hw.getTowerPosition()
        self.moving = False
        super(PageTowerMove, self).show()
    #enddef


    def _up(self, slowMoving):
        if not self.moving:
            if self.setProfiles:
                self.display.hw.setTowerProfile('moveSlow' if slowMoving else 'homingFast')
            #endif
            self.display.hw.towerToMax()
            self.moving = True
        else:
            if self.display.hw.isTowerOnMax():
                self.display.hw.beepAlarm(1)
            #endif
            self.showItems(value = self.display.hw.getTowerPosition())
        #endif
    #enddef


    def _down(self, slowMoving):
        if not self.moving:
            if self.setProfiles:
                self.display.hw.setTowerProfile('moveSlow' if slowMoving else 'homingFast')
            #endif
            self.display.hw.towerToMin()
            self.moving = True
        else:
            if self.display.hw.isTowerOnMin():
                self.display.hw.beepAlarm(1)
            #endif
            self.showItems(value = self.display.hw.getTowerPosition())
        #endif
    #enddef


    def _stop(self):
        self.display.hw.towerStop()
        self.moving = False
    #enddef


    def changeProfiles(self, setProfiles):
        self.setProfiles = setProfiles
    #enddef

#endclass


@page
class PageTiltMove(MovePage):
    Name = "tiltmove"

    def __init__(self, display):
        super(PageTiltMove, self).__init__(display)
        self.pageUI = "tiltmove"
        self.pageTitle = N_("Tilt Move")
        self.autorepeat = { "upfast" : (1, 1), "upslow" : (1, 1), "downfast" : (1, 1), "downslow" : (1, 1) }
        self.setProfiles = True
    #enddef


    def show(self):
        self.items["value"] = self.display.hw.getTiltPosition()
        self.moving = False
        super(PageTiltMove, self).show()
    #enddef


    def _up(self, slowMoving):
        if not self.moving:
            if self.setProfiles:
                self.display.hw.setTiltProfile('moveSlow' if slowMoving else 'homingFast')
            #endif
            self.display.hw.tiltToMax()
            self.moving = True
        else:
            if self.display.hw.isTiltOnMax():
                self.display.hw.beepAlarm(1)
            #endif
            self.showItems(value = self.display.hw.getTiltPosition())
        #endif
    #enddef


    def _down(self, slowMoving):
        if not self.moving:
            if self.setProfiles:
                self.display.hw.setTiltProfile('moveSlow' if slowMoving else 'homingFast')
            #endif
            self.display.hw.tiltToMin()
            self.moving = True
        else:
            if self.display.hw.isTiltOnMin():
                self.display.hw.beepAlarm(1)
            #endif
            self.showItems(value = self.display.hw.getTiltPosition())
        #endif
    #enddef


    def _stop(self):
        self.display.hw.tiltStop()
        self.moving = False
    #enddef


    def changeProfiles(self, setProfiles):
        self.setProfiles = setProfiles
    #enddef

#endclass


@page
class PageTowerOffset(MovePage):
    Name = "toweroffset"

    def __init__(self, display):
        super(PageTowerOffset, self).__init__(display)
        self.pageUI = "towermovecalibration"
        self.pageTitle = N_("Tower Offset")
        self.stack = False
        self.autorepeat = { "upslow" : (3, 1), "downslow" : (3, 1) }
    #enddef


    def show(self):
        self.tmpTowerOffset = self.display.hwConfig.calibTowerOffset
        self.items["value"] = self._strOffset(self.tmpTowerOffset)
        super(PageTowerOffset, self).show()
    #enddef


    def _value(self, change):
        if -400 <= self.tmpTowerOffset + change <= 400:
            self.tmpTowerOffset += change
            self.showItems(**{ 'value' : self._strOffset(self.tmpTowerOffset) })
        else:
            self.display.hw.beepAlarm(1)
        #endif
    #enddef


    def upslowButton(self):
        self._value(1)
    #enddef


    def upslowButtonRelease(self):
        pass
    #enddef


    def downslowButton(self):
        self._value(-1)
    #enddef


    def downslowButtonRelease(self):
        pass
    #enddef


    def okButtonRelease(self):
        self.display.hwConfig.calibTowerOffset = self.tmpTowerOffset
        try:
            self.display.hwConfig.write()
        except ConfigException:
            self.logger.exception("Cannot save configuration")
            self.display.pages['error'].setParams(
                text=_("Cannot save configuration"))
            return "error"
        #endtry
        return "_BACK_"
    #enddef

#endclass
