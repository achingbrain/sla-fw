# This file is part of the SLA firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2022 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

from glob import glob

from setuptools import setup, find_packages

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
    package_data={'slafw': ['data/*', 'data/*/*']},
    data_files=data_files,
    url="https://gitlab.com/prusa3d/sl1/sla-fw",
    license="GNU General Public License v3 or later (GPLv3+)",
    classifiers=[
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)'
    ]
)
