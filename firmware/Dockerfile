FROM ubuntu:19.04

ENV TZ=Etc/UTC
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Install native deps
RUN apt-get update && apt-get install -y python3 python3-pip python3-pygame python3-paho-mqtt python3-systemd python3-serial python3-pyroute2 python3-numpy python3-jinja2 python3-pydbus python3-gi python3-bitstring python3-toml python3-mock pylint3 # python3-future python3-six

# Install python deps
RUN pip3 install websocket-server gpio lazy-import

# Create use that will run the build
RUN useradd --create-home --user-group appuser
USER appuser
WORKDIR /home/appuser/

