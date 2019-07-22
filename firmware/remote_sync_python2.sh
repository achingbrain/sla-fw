#!/bin/sh
SL1=$1

if [ -z ${SL1} ]; then
	echo "Pass target as the only argument";
	exit -1;
fi;

rsync -av nginx/sl1fw ${SL1}:/etc/nginx/sites-available/ &&
rsync -av systemd/sl1fw.service ${SL1}:/lib/systemd/system/sl1fw.service &&
rsync -av systemd/sl1fw-tmpfiles.conf ${SL1}:/lib/tmpfiles.d/sl1fw-tmpfiles.conf &&
rsync -av sl1fw/intranet/ ${SL1}:/srv/http/intranet/ &&
rsync -av sl1fw/scripts/ ${SL1}:/usr/share/sl1fw/scripts/ &&
rsync -av sl1fw/multimedia/ ${SL1}:/usr/share/sl1fw/multimedia/ &&
rsync -av --exclude intranet --exclude scripts --exclude multimedia sl1fw/ ${SL1}:/usr/lib/python2.7/site-packages/sl1fw/

ssh ${SL1} systemctl restart sl1fw
