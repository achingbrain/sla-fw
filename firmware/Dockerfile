FROM ubuntu:eoan

ENV TZ=Etc/UTC
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Install native deps
RUN apt-get update && apt-get install -y python3 python3-pip python3-paho-mqtt python3-systemd python3-serial python3-numpy python3-jinja2 python3-pydbus python3-gi python3-bitstring python3-toml python3-mock python3-future \
git openssh-client build-essential xxd gawk gettext python3-coverage python3-networkmanager python3-dbusmock python3-pil python3-distro python3-sphinx python3-psutil python3-deprecated python3-evdev lftp

# Install python deps
RUN pip3 install websocket-server gpio readerwriterlock pylint pysignal

# Create use that will run the build
RUN useradd --create-home --user-group appuser
USER appuser
WORKDIR /home/appuser/

# Setup ssh to trust git server
RUN mkdir -p .ssh
RUN chmod 700 .ssh
RUN ssh-keyscan gitlab.com >> .ssh/known_hosts

