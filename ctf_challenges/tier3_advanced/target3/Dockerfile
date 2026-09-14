FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt update && apt install -y openssh-server sudo && rm -rf /var/lib/apt/lists/*
RUN mkdir /var/run/sshd
RUN useradd -m -s /bin/bash vaultadmin
RUN mkdir -p /home/vaultadmin/.ssh
COPY key_t2_t3.pub /home/vaultadmin/.ssh/authorized_keys
RUN chown -R vaultadmin:vaultadmin /home/vaultadmin/.ssh && chmod 700 /home/vaultadmin/.ssh && chmod 600 /home/vaultadmin/.ssh/authorized_keys

# Sudo rule to read flag or privesc
RUN echo "vaultadmin ALL=(ALL) NOPASSWD: /usr/bin/systemctl" >> /etc/sudoers
RUN mkdir -p /vault && echo "FLAG{ANTANOM_TIER3_RBASH_MULTIHOP_VAULT_9942}" > /vault/flag.txt && chmod 600 /vault/flag.txt

EXPOSE 22
CMD ["/usr/sbin/sshd", "-D"]
