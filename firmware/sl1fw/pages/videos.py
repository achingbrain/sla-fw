# part of SL1 firmware
# 2014-2018 Futur3d - www.futur3d.net
# 2018-2019 Prusa Research s.r.o. - www.prusa3d.com

from sl1fw import defines
from sl1fw.libPages import page, Page


@page
class PageVideos(Page):
    Name = "videos"

    def __init__(self, display):
        super(PageVideos, self).__init__(display)
        self.pageUI = "videos"
        self.pageTitle = N_("Videos")
        self.items.update({
            'videos_url': defines.videosURL,
            #'text' : "",
        })
    #enddef

#endclass
