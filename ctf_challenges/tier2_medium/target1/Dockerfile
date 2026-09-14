FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y     python3 python3-flask cron curl net-tools iproute2 iputils-ping     && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash appuser

RUN mkdir -p /opt/scripts &&     echo '#!/bin/bash\necho backup ok > /tmp/backup.status' > /opt/scripts/backup.sh &&     chmod 777 /opt/scripts/backup.sh

RUN echo '* * * * * root /opt/scripts/backup.sh' > /etc/cron.d/backup_job &&     chmod 0644 /etc/cron.d/backup_job

RUN mkdir -p /opt/config &&     echo 'INTERNAL_API_TOKEN=s3cr3t_m3d1um_t0k3n_9918\nINTERNAL_TARGET=172.23.0.20' > /opt/config/.env &&     chmod 644 /opt/config/.env

WORKDIR /app
COPY app.py .

EXPOSE 8443
CMD service cron start && su - appuser -c "python3 /app/app.py"
