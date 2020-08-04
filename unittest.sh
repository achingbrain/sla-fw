#!/bin/sh

set -x

export PATH="${PATH}:$(pwd)"

if ! command -v SLA-control-01.elf
then
    echo "SLA-control-01.elf not found. Did you forgot to run build_sim.sh?"
    exit 2
fi

cd firmware &&
python3-coverage run -m unittest discover --failfast --verbose sl1fw.tests.unittests &&
python3-coverage report --include "sl1fw*"
