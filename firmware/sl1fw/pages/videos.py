# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from sl1fw import defines
from sl1fw.pages import page
from sl1fw.pages.base import Page


@page
class PageVideos(Page):
    Name = "videos"

    def __init__(self, display):
        super(PageVideos, self).__init__(display)
        self.pageUI = "videos"
        self.items.update({
            'videos_url': defines.videosURL,
            #'text' : "",
        })
    #enddef

#endclass
