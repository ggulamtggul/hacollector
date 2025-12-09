FROM python:3.11-slim

# 필요한 패키지 설치 (procps는 pgrep을 위해 필요)
RUN apt-get update && apt-get install -y tzdata procps && rm -rf /var/lib/apt/lists/*
ENV TZ="Asia/Seoul"

WORKDIR /hacollector

COPY requirements.txt /hacollector
RUN pip3 install --no-cache-dir -r requirements.txt

RUN mkdir -p /hacollector/classes
COPY hacollector.py /hacollector
COPY classes/*.py /hacollector/classes/
COPY config.py /hacollector
COPY consts.py /hacollector
COPY hacollector.conf.example /hacollector

# Healthcheck: Check if /tmp/healthy was touched in the last minute
# This confirms the main loop is active and not deadlocked
HEALTHCHECK --interval=60s --timeout=5s --start-period=30s --retries=3 \
  CMD test $(find /tmp/healthy -mmin -1) || exit 1

# Python 직접 실행
CMD [ "python3", "/hacollector/hacollector.py" ]