from setuptools import setup, find_packages
from glob import glob
from os import chmod, walk, path
from stat import S_IRUSR



data_files=[]
data_files.append(('/usr/share/sl1fw/scripts', glob('sl1fw/scripts/*')))
data_files.append(('/usr/share/sl1fw/multimedia', glob('sl1fw/multimedia/*')))
data_files.append(('/etc/sl1fw', ['sl1fw/hardware.cfg']))
data_files.append(('/usr/lib/systemd/system', ['systemd/sl1fw.service']))
data_files.append(('/usr/lib/tmpfiles.d/', ['systemd/sl1fw-tmpfiles.conf']))
data_files.append(('/etc/nginx/sites-available', ['nginx/sl1fw']))

for root, dirs, files in walk('sl1fw/intranet'):
	data_files.append((path.join("/srv/http/intranet/", path.relpath(root, 'sl1fw/intranet')), [path.join(root, filename) for filename in files]))

print(data_files)

setup(
	name="sl1fw",
	version="0.1",
	packages=find_packages(),
	scripts=['sl1fw/main.py'],
	package_data={'sl1fw': ['data/*']},
	data_files=data_files
)
