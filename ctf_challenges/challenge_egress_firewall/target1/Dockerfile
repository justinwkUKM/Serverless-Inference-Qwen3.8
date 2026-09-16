FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 python3-flask iptables curl net-tools iproute2 iputils-ping sudo \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash appuser

WORKDIR /app
COPY app.py /app/app.py
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8085
ENTRYPOINT ["/entrypoint.sh"]
