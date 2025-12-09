FROM python:3.11-slim

# 필요한 패키지 설치 (procps는 pgrep을 위해 필요, jq는 제거)
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
# RUN chmod +x run.sh (Not needed)

# 간단한 헬스체크: 메인 프로세스가 실행 중인지 확인
HEALTHCHECK --interval=60s --timeout=5s --start-period=30s --retries=3 \
  CMD pgrep -f "hacollector.py" || exit 1

# Python 직접 실행 (SHELL 모드 사용 권장)
CMD ["python3", "hacollector.py"]