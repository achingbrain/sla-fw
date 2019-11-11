#!/bin/zsh

# This file is part of the SL1 firmware
# Copyright (C) 2014-2018 Futur3d - www.futur3d.net
# Copyright (C) 2018-2019 Prusa Research s.r.o. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

rm -f *job* *.pdf

for i in *.xz; do xz -d $i; done
for i in log.*.txt; do echo "Splitting $i"; csplit --quiet --prefix="${${i#*.}%%.*}-job-" $i "/AllItems: toPrint/" "{*}"; done
for i in *-job-??; do echo "Splitting $i"; csplit --quiet --prefix=$i- $i "/Job finished/" "{*}"; done
for i in `grep -l 'Temperatures.*-' *-job-??-??`; do echo "Removing $i" ; rm -f $i; done
for i in *-job-??-??; do echo -n "${i%%-*} - " > $i.time; grep 'Temperatures' $i |head -n1|cut -d " " -f -3 >> $i.time; done
for i in *-job-??-??; do echo "Collecting data from $i"; grep 'Temperatures' $i | cut -d " " -f 3,12- | ./linear_time.py > $i.csv; done
for i in *.csv; do [[ `wc -l $i|cut -d " " -f1 -` -lt 200 ]] && rm -f $i ; done
for i in *.csv; do echo "Plotting $i"; gnuplot -e "set title \"`cat ${i%.csv}.time`\"" temperature_graph.gnu < $i > ${i%.csv}.svg; done
for i in *.svg; do echo "Converting $i"; rsvg-convert -f pdf -o ${i%.svg}.pdf $i; done
#pdfunite *.pdf temperature_graphs.pdf
