#!/bin/sh

set -x

export PYTHONPATH="$(pwd)$(find ./dependencies/ -maxdepth 1 -type d -printf ':.%p')"
cd firmware

echo "Using pylint version:"
python3 -m pylint --version

python3 -m pylint --persistent=n --jobs 0 --additional-builtins=_,N_,ngettext --max-line-length=120 --disable similarities,duplicate-code,fixme,missing-docstring --disable bad-continuation,bad-whitespace,invalid-name,broad-except,line-too-long,unbalanced-tuple-unpacking,isinstance-second-argument-not-valid-type,invalid-bytes-returned,super-with-arguments sl1fw
