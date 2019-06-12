from sl1fw.libPages import Page, page


@page
class PageStart(Page):
    Name = "start"

    def __init__(self, display):
        super(PageStart, self).__init__(display)
    #enddef

#endclass