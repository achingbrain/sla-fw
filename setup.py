# This file is part of the SLA firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import subprocess
from glob import glob

import setuptools.command.build_py
from setuptools import setup, find_packages


class BuildPyWithLocalesCommand(setuptools.command.build_py.build_py):
    def run(self):
        subprocess.check_call(["make", "-C", "slafw/locales"])
        setuptools.command.build_py.build_py.run(self)


data_files = [
    ('/usr/share/slafw/scripts', glob('slafw/scripts/*')),
    ('/etc/sl1fw', ['slafw/hardware.cfg']),
    ('/etc/sl1fw', ['slafw/loggerConfig.json']),
    ('/usr/lib/systemd/system', glob('systemd/*.service')),
    ('/usr/lib/tmpfiles.d/', ['systemd/slafw-tmpfiles.conf']),
    ('/usr/share/dbus-1/system.d', glob('dbus/*'))
]

setup(
    name="slafw",
    version="2022.01.11",
    packages=find_packages(exclude=["slafw.tests"]),
    scripts=['slafw/main.py', 'slafw/scripts/export_logs.bash'],
    package_data={'slafw': ['data/*', 'data/*/*', 'locales/*/LC_MESSAGES/*.mo']},
    data_files=data_files,
    cmdclass={
        'build_py': BuildPyWithLocalesCommand
    },
    url="https://gitlab.com/prusa3d/sl1/sla-fw",
    license="GNU General Public License v3 or later (GPLv3+)",
    classifiers=[
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)'
    ]
)
