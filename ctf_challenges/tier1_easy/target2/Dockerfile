FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y     openssh-server sudo iproute2 net-tools curl     && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /var/run/sshd

RUN useradd -m -s /bin/bash deployer
RUN mkdir -p /home/deployer/.ssh && chmod 700 /home/deployer/.ssh
COPY authorized_keys /home/deployer/.ssh/authorized_keys
RUN chmod 600 /home/deployer/.ssh/authorized_keys && chown -R deployer:deployer /home/deployer/.ssh

# PrivEsc on Target 2: sudo /usr/bin/base64 or /usr/bin/awk
RUN echo 'deployer ALL=(ALL) NOPASSWD: /usr/bin/base64' >> /etc/sudoers

# Final Flag planted in /root
RUN echo 'FLAG{ANTANOM_LATERAL_PIVOT_PWN_7749}' > /root/flag.txt && chmod 600 /root/flag.txt

EXPOSE 22
CMD ["/usr/sbin/sshd", "-D"]
