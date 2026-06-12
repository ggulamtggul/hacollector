ARG BUILD_FROM
FROM ${BUILD_FROM}

# Labels for HA Supervisor
LABEL io.hass.version="2.0.0" io.hass.type="addon" io.hass.arch="aarch64|amd64"

# Ensure python3 and pip exist (fallback for non-python base images)
RUN command -v python3 >/dev/null 2>&1 || apk add --no-cache python3 py3-pip

WORKDIR /hacollector

COPY requirements.txt /hacollector
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# Copy application
RUN mkdir -p /hacollector/classes
COPY hacollector.py /hacollector
COPY classes/*.py /hacollector/classes/
COPY config.py /hacollector
COPY consts.py /hacollector

# Run script
COPY run.sh /
RUN chmod a+x /run.sh

# Healthcheck: Check if /tmp/healthy was touched in the last minute
HEALTHCHECK --interval=60s --timeout=5s --start-period=60s --retries=3 \
  CMD test $(find /tmp/healthy -mmin -1) || exit 1

CMD [ "/run.sh" ]