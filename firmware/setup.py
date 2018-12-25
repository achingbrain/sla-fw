from setuptools import setup, find_packages
from glob import glob
from os import chmod
from stat import S_IRUSR

chmod('sl1fw/scripts/rsync-key', S_IRUSR)

setup(
    name="sl1fw",
    version="0.1",
    packages=find_packages(),
    scripts=['sl1fw/main.py'],
    package_data={'sl1fw': ['data/*']},
    data_files=[('/usr/share/sl1fw/scripts', glob('sl1fw/scripts/*')),
                ('/etc/sl1fw', ['sl1fw/hardware.cfg']),
                ('/srv/http/intranet', glob('sl1fw/intranet/*.html')),
                ('/srv/http/intranet/templates', glob('sl1fw/intranet/templates/*.html')),
                ('/srv/http/intranet/static', glob('sl1fw/intranet/static/*')),
                ('/usr/lib/systemd/system', ['systemd/sl1fw.service']),
                ('/usr/lib/tmpfiles.d/', ['systemd/sl1fw-tmpfiles.conf']),
                ('/etc/nginx/sites-available', ['nginx/sl1fw'])]
)
