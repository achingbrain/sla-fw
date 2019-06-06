#!/bin/sh

CFG="/etc/sl1fw/hardware.cfg"

# Resolve target
if [ "$#" -ne 1 ]; then
    echo "Please provide target ip as the only argument"
    exit -1
fi
target=${1}
echo "Target is ${target}"

# Print commands being executed
set -o xtrace

# Create temp root
tmp=$(mktemp --directory --tmpdir=/tmp/ sl1fw.XXXX)
echo "Local temp is ${tmp}"

echo "Running setup"
python2 setup.py sdist --dist-dir=${tmp}

# Create remote temp
target_tmp=$(ssh root@${target} "mktemp --directory --tmpdir=/tmp/ sl1fw.XXXX")
echo "Remote temp is ${target_tmp}"

echo "Install on target...start"
scp -r ${tmp}/* root@${target}:${target_tmp}
ssh root@${target} "\
set -o xtrace; \
cp -f \"$CFG\" \"$CFG.bak\"; \
cd ${target_tmp}; \
tar xvf sl1fw*.tar.gz; \
rm sl1fw*.tar.gz; \
cd sl1fw-*; \
pip install . ; \
mv -f \"$CFG\" \"$CFG.new\"; \
cp \"$CFG.bak\" \"$CFG\"; \
systemctl daemon-reload; \
systemctl restart sl1fw
"
echo "Install on target...done"

echo "Removing remote temp"
ssh root@${target} "rm -rf ${target_tmp}"

echo "Removing local temp"
rm -rf ${tmp}
