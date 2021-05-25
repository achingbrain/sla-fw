# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import subprocess
from glob import glob

import setuptools.command.build_py
from setuptools import setup, find_packages


class BuildPyWithLocalesCommand(setuptools.command.build_py.build_py):
    def run(self):
        subprocess.check_call(["make", "-C", "sl1fw/locales"])
        setuptools.command.build_py.build_py.run(self)


data_files = [
    ('/usr/share/sl1fw/scripts', glob('sl1fw/scripts/*')),
    ('/usr/share/sl1fw/multimedia', glob('sl1fw/multimedia/*.xm')),
    ('/usr/share/sl1fw/multimedia/SL1', glob('sl1fw/multimedia/SL1/*')),
    ('/usr/share/sl1fw/multimedia/SL1S', glob('sl1fw/multimedia/SL1S/*')),
    ('/etc/sl1fw', ['sl1fw/hardware.cfg']),
    ('/etc/sl1fw', ['sl1fw/loggerConfig.json']),
    ('/usr/lib/systemd/system', glob('systemd/*.service')),
    ('/usr/lib/tmpfiles.d/', ['systemd/sl1fw-tmpfiles.conf']),
    ('/usr/share/factory/defaults', ['factory/factory.toml']),
    ('/usr/share/dbus-1/system.d', glob('dbus/*'))
]

setup(
    name="sl1fw",
    version="2021.04.14",
    packages=find_packages(exclude=["sl1fw.tests"]),
    scripts=['sl1fw/main.py', 'sl1fw/scripts/export_logs.bash'],
    package_data={'sl1fw': ['data/*', 'data/SL*/*', 'locales/*/LC_MESSAGES/*.mo']},
    data_files=data_files,
    cmdclass={
        'build_py': BuildPyWithLocalesCommand
    },
    url="https://gitlab.com/prusa3d/sl1/a64-fw",
    license="GNU General Public License v3 or later (GPLv3+)",
    classifiers=[
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)'
    ]
)
