from setuptools import setup, find_packages
import setuptools.command.build_py
from glob import glob
from os import walk, path
import subprocess


class BuildPyWithLocalesCommand(setuptools.command.build_py.build_py):
    def run(self):
        subprocess.check_call(["make", "-C", "sl1fw/locales"])
        setuptools.command.build_py.build_py.run(self)


data_files = [
    ('/usr/share/sl1fw/scripts', glob('sl1fw/scripts/*')),
    ('/usr/share/sl1fw/multimedia', glob('sl1fw/multimedia/*')),
    ('/etc/sl1fw', ['sl1fw/hardware.cfg']),
    ('/usr/lib/systemd/system', ['systemd/sl1fw.service']),
    ('/usr/lib/tmpfiles.d/', ['systemd/sl1fw-tmpfiles.conf']),
    ('/etc/nginx/sites-available', ['nginx/sl1fw']),
    ('/usr/share/factory/defaults', ['factory/factory.toml']),
    ('/usr/share/dbus-1/system.d', ['dbus/cz.prusa3d.sl1.printer0.conf'])
]


for root, dirs, files in walk('sl1fw/intranet'):
    target = path.join("/srv/http/intranet/", path.relpath(root, 'sl1fw/intranet'))
    content = [path.join(root, filename) for filename in files]
    data_files.append((target, content))

setup(
    name="sl1fw",
    version="0.1",
    packages=find_packages(exclude=["sl1fw.tests"]),
    scripts=['sl1fw/main.py'],
    package_data={'sl1fw': ['data/*', 'locales/*/LC_MESSAGES/*.mo']},
    data_files=data_files,
    cmdclass={
        'build_py': BuildPyWithLocalesCommand
    }
)
