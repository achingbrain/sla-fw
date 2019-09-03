#!/usr/bin/python

import sys

start = -1
last = 0

for line in sys.stdin:
    items = line.strip().split(" ")
    timeparts = items[0].split(":")
    seconds = int(timeparts[0]) * 3600 + int(timeparts[1]) * 60 + int(timeparts[2])
    if seconds < last:
        seconds += 24 * 3600
    last = seconds
    if start < 0:
        start = seconds
    print(seconds - start, items[1], items[2], items[3], items[4])
