#!/usr/bin/env bash

curl http://10.24.10.12/images/current.raucb --output /tmp/current.raucb --progress-bar &&
rauc install /tmp/current.raucb