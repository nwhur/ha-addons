ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:latest
FROM $BUILD_FROM

ENV LANG C.UTF-8
ENV PYTHONUNBUFFERED=1

# Install requirements
RUN apk add --no-cache python3 py3-pip
RUN pip3 install --no-cache-dir paho-mqtt --break-system-packages

# Copy data
COPY run.sh /
COPY humicon_daemon.py /

RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
