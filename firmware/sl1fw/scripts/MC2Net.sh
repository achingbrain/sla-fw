#!/bin/bash

DEV=$1
PORT=$2
socat "tcp-l:$PORT,reuseaddr,fork" "file:$DEV,nonblock,raw,echo=0,waitlock=/var/run/tty,b115200"
