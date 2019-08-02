FROM ubuntu:19.04

ENV TZ=Etc/UTC
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Install native deps
RUN apt-get update && apt-get install -y python2.7 python-pip python-pygame python-paho-mqtt python-systemd python-serial python-pyroute2 python-numpy python-six python-jinja2 python-pydbus python-gi python-bitstring python-toml python-mock python-future python-monotonic \
python3 python3-pip python3-pygame python3-paho-mqtt python3-systemd python3-serial python3-pyroute2 python3-numpy python3-six python3-jinja2 python3-pydbus python3-gi python3-bitstring python3-toml python3-mock python3-future pylint pylint3 \
git openssh-client build-essential xxd gawk
RUN apt-get update && apt-get install -y gettext
RUN apt-get update && apt-get install -y python3-coverage

# Install python deps
RUN pip2 install websocket-server gpio lazy-import logging
RUN pip3 install websocket-server gpio lazy-import

# Create use that will run the build
RUN useradd --create-home --user-group appuser
USER appuser
WORKDIR /home/appuser/

# Setup ssh to trust git server
RUN mkdir -p .ssh
RUN chmod 700 .ssh
RUN ssh-keyscan gitlab.com >> .ssh/known_hosts

