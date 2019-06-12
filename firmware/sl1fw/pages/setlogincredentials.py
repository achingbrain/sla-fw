import subprocess

from sl1fw.libPages import page, Page


@page
class PageSetLoginCredentials(Page):
    Name = "setlogincredentials"

    def __init__(self, display):
        super(PageSetLoginCredentials, self).__init__(display)
        self.pageUI = "setlogincredentials"
        self.pageTitle = N_("Login Credentials")
    #enddef


    def fillData(self):
        return {
            'api_key' : self.octoprintAuth,
        }
    #enddef


    def show(self):
        self.items.update(self.fillData())
        super(PageSetLoginCredentials, self).show()
    #enddef


    def saveButtonSubmit(self, data):
        apikey = data['api_key']

        try:
            subprocess.check_call(["/bin/api-keygen.sh", apikey])
        except subprocess.CalledProcessError as e:
            self.display.pages['error'].setParams(
                text = _("Octoprint API key change failed"))
            return "error"
        #endexcept

        return "_BACK_"
    #enddef

#endclass