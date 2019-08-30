class Printer0:
    """
    This is public a printer API placeholder.
    """

    INTERFACE = "cz.prusa3d.sl1.printer0"
    dbus = """
        <node>
            <interface name='%s'>
            </interface>
        </node>
    """ % INTERFACE

    def __init__(self, printer):
        self.printer = printer

