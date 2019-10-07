#!/usr/bin/env bash

if [ -n "${1}" ]; then
        LOG_PATH=$1
else
        PATTERN="/run/media/root/*"
        USBS=( ${PATTERN} )
        LOG_PATH=${USBS[0]}/log.emergency.txt.xz
fi;

echo "${LOG_PATH}"

(
        for i in $(journalctl --list-boots | awk '{print $1}'); do
                echo "########## REBOOT: ${i} ##########";
                journalctl --no-pager --boot "${i}";
        done;
) | xz -T0 -0 > "${LOG_PATH}"
sync "${LOG_PATH}"