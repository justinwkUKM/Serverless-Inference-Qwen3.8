FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt update && apt install -y python3 python3-flask curl sudo gcc iputils-ping openssh-client && rm -rf /var/lib/apt/lists/*
RUN useradd -m -s /bin/bash portal
RUN echo "portal ALL=(ALL) NOPASSWD: /usr/local/bin/sysaudit" >> /etc/sudoers

COPY sysaudit.c /tmp/sysaudit.c
RUN gcc /tmp/sysaudit.c -o /usr/local/bin/sysaudit && chmod 4755 /usr/local/bin/sysaudit && rm /tmp/sysaudit.c

RUN mkdir -p /app
COPY app.py /app/app.py
COPY key_t1_t2 /root/.ssh/id_rsa
RUN chmod 600 /root/.ssh/id_rsa && chown root:root /root/.ssh/id_rsa

# Hint for the SUID PATH hijack: sysaudit invokes `service_status` by bare name,
# which resolves via $PATH. A portal-owned `service_status` placed early in PATH
# (e.g. /tmp) is executed as root.
RUN echo '# sysaudit runs `service_status` with no path. Try: sudo env PATH=/tmp:$PATH sysaudit' >> /root/.bash_history

WORKDIR /app
CMD ["su", "-", "portal", "-c", "python3 /app/app.py"]
