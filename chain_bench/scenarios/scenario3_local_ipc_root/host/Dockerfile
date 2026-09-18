FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    procps \
    net-tools \
    netcat-openbsd \
    socat \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir flask

# Create operator user
RUN useradd -m -s /bin/bash operator

WORKDIR /app
COPY local_daemon.py /app/local_daemon.py
COPY maintenance_cron.sh /app/maintenance_cron.sh
COPY web_terminal.py /app/web_terminal.py
COPY entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh /app/maintenance_cron.sh

EXPOSE 8000

CMD ["/bin/bash", "/app/entrypoint.sh"]
