#!/bin/bash

HEX="$1/SLA-control_rev0$2.hex"
PORT=$3
avrdude -p ATmega32u4 -P "$PORT" -c avr109 -F -v -u -V -U "flash:w:$HEX:i"
