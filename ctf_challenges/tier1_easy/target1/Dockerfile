FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y     python3 python3-pip python3-flask sudo openssh-client curl net-tools iproute2 iputils-ping     && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash www-data-user &&     echo 'www-data-user ALL=(ALL) NOPASSWD: /usr/bin/find' >> /etc/sudoers

RUN mkdir -p /root/.ssh && chmod 700 /root/.ssh
COPY id_rsa /root/.ssh/id_rsa
RUN chmod 600 /root/.ssh/id_rsa

# Hint in root bash history or notes
RUN echo 'ssh -o StrictHostKeyChecking=no deployer@172.21.0.20' > /root/.bash_history

WORKDIR /app
COPY app.py .

EXPOSE 8080
CMD ["su", "-", "www-data-user", "-c", "python3 /app/app.py"]
