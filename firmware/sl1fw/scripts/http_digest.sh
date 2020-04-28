#!/usr/bin/env bash

# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

FILE=/etc/nginx/sites-available/sl1fw 
case $1 in
    "disable")
        sed -i 's/include\s*\/etc\/nginx/# include \/etc\/nginx/' $FILE
        systemctl reload nginx
    ;;
    "enable")
        sed -i 's/# include\s*\/etc\/nginx/include \/etc\/nginx/' $FILE
        systemctl reload nginx
    ;;
esac
