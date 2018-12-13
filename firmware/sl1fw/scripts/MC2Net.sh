#!/bin/bash

DEV=$1
PORT=$2
BAUD=$3
socat "tcp-l:$PORT,reuseaddr,fork" "file:$DEV,nonblock,raw,echo=0,waitlock=/var/run/tty,b$BAUD"
