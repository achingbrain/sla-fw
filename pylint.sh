#!/bin/sh

set -x

export PYTHONPATH="$(pwd)$(find ./dependencies/ -maxdepth 1 -type d -printf ':%p')"

echo "Using pylint version:"
python3 -m pylint --version

# python3 -m black sl1fw
python3 -m pylint sl1fw
