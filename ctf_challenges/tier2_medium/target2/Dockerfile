FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y     python3 python3-pip python3-flask sudo net-tools iproute2 curl     && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash svc_runner

RUN mkdir -p /opt && \
    echo 'import custom_logger\nprint("System metrics recorded")' > /opt/monitor.py && \
    echo 'def log(): pass' > /opt/custom_logger.py && \
    chmod 777 /opt /opt/custom_logger.py

# Sudo rule: svc_runner can run python /opt/monitor.py without password
RUN echo 'svc_runner ALL=(ALL) NOPASSWD: /usr/bin/python3 /opt/monitor.py *' >> /etc/sudoers

# Plant Tier 2 Flag
RUN echo 'FLAG{ANTANOM_TIER2_SSTI_CRON_PIVOT_8821}' > /root/flag.txt && chmod 600 /root/flag.txt

WORKDIR /app
COPY app.py .

EXPOSE 8000
CMD su - svc_runner -c "python3 /app/app.py"
