# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import os

from sl1fw import defines
from sl1fw.pages import page
from sl1fw.libPages import Page


class PageMedia(Page):

    def __init__(self, display):
        super(PageMedia, self).__init__(display)
        self.base_path = defines.multimediaRootPath
        self.path = None
    #enddef


    def setMedia(self, relative_path):
        self.path = relative_path
    #enddef


    def fillData(self):
        return {
            'relative_path' : self.path,
            'base_path' : self.base_path,
            'absolute_path' : os.path.join(self.base_path, self.path),
        }
    #enddef


    def show(self):
        self.items.update(self.fillData())
        super(PageMedia, self).show()
    #enddef

#endclass


@page
class PageImage(PageMedia):
    Name = "image"

    def __init__(self, display):
        super(PageImage, self).__init__(display)
        self.pageUI = "image"
        self.pageTitle = N_("Image")
        self.path = None
    #enddef

#endclass


@page
class PageVideo(PageMedia):
    Name = "video"

    def __init__(self, display):
        super(PageVideo, self).__init__(display)
        self.pageUI = "video"
        self.pageTitle = N_("Video")
        self.path = None
    #enddef

#endclass
